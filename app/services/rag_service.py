import asyncio
import io
import re
import uuid
from typing import Annotated, List, TypedDict

import PyPDF2
from fastapi import Depends
from langchain.text_splitter import RecursiveCharacterTextSplitter  # Or your custom splitter
from odmantic import ObjectId
from openai import AsyncOpenAI
from pinecone import Pinecone, ServerlessSpec  # type:ignore # Add ServerlessSpec import

# from pinecone.core.openapi.data.models import Vector
from app.config.logging_config import logger

# from tenacity import retry, stop_after_attempt, wait_random_exponential
from app.config.settings import settings
from app.models.conversation import Conversation
from app.services.mongo_service import MongoService, get_mongo_service
from app.services.pdf_service import PDFService, get_pdf_service


class Vector(TypedDict):
    id: str  # Change from bytes to str
    values: list[float]
    metadata: dict


class RagService:
    def __init__(self, mongo_service: MongoService, pdf_service: PDFService):
        self.mongo_service = mongo_service
        self.pdf_service = pdf_service
        self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.batch_size = 5000

        # Initialize Pinecone client
        self.pc = Pinecone(api_key=settings.pinecone_api_key)
        self.index_name = "llm-chat-index"

        # Check and create index with serverless spec
        if self.index_name not in self.pc.list_indexes().names():
            self.pc.create_index(
                name=self.index_name,
                dimension=1536,
                metric="cosine",
                spec=ServerlessSpec(  # Add serverless configuration
                    cloud="aws",      # Match your original environment
                    region="us-east-1" # Adjusted region format
                )
            )

        # Get index reference
        self.index = self.pc.Index(self.index_name)

    async def insert_to_rag(self, conversation_id: str):
        """
        Simplified RAG insertion with better text normalization
        """
        # Get conversation with processing state
        conversation = await self.mongo_service.engine.find_one(
            Conversation,
            Conversation.id == ObjectId(conversation_id)
        )
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        # Find unprocessed files
        file_cursor = self.mongo_service.sync_fs.find(
            {"metadata.conversation_id": str(conversation_id)}
        )
        unprocessed = [
            file._id for file in file_cursor
            if file._id not in conversation.uploaded_files_ids
        ]

        if not unprocessed:
            return

        try:
            # Process PDFs and extract clean text
            text = await self._process_pdfs_to_text(conversation_id, unprocessed)
            chunks = self._split_text_with_cleanup(text)

            # Process embeddings in streamlined batches
            await self._process_embeddings_batches(conversation, chunks)

            # Update processing state
            conversation.uploaded_files_ids.extend(unprocessed)
            await self.mongo_service.engine.save(conversation)

        except Exception as e:
            logger.error(f"RAG insertion failed: {str(e)}")
            raise

    async def _process_pdfs_to_text(self, conversation_id: str, file_ids: list) -> str:
        """Process PDFs into clean normalized text"""
        text_buffer = []

        # Process files individually to maintain error isolation
        for file_id in file_ids:
            try:
                grid_out = await self.mongo_service.async_fs.open_download_stream(file_id)
                if not grid_out:
                    continue

                # Stream PDF content directly
                pdf_bytes = await grid_out.read()
                text = await self._extract_text_from_pdf(pdf_bytes)
                text_buffer.append(text)

            except Exception as e:
                logger.warning(f"Failed to process file {file_id}: {str(e)}")
                continue

        return "\n".join(text_buffer)

    async def _extract_text_from_pdf(self, pdf_bytes: bytes) -> str:
        """Extract and normalize text from PDF bytes"""
        text = []

        with io.BytesIO(pdf_bytes) as pdf_file:
            reader = PyPDF2.PdfReader(pdf_file)
            for page in reader.pages:
                page_text = page.extract_text() or ""
                # Normalize whitespace and clean text
                cleaned = re.sub(r'\s+', ' ', page_text).strip()
                text.append(cleaned)

        return " ".join(text).strip()

    def _split_text_with_cleanup(self, text: str) -> List[str]:
        """Split text with proper chunking and cleanup"""
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n", ". ", "! ", "? ", "; ", " ", ""]
        )
        return splitter.split_text(text)

    async def _process_embeddings_batches(self, conversation: Conversation, chunks: List[str]):
        """Handle embedding generation and Pinecone upserts"""
        BATCH_SIZE = 500  # Reduced from original 1000 for safety
        
        for i in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[i:i+BATCH_SIZE]
            embeddings = await self._get_batch_embeddings(batch)
            
            vectors = [{
                "id": f"{conversation.user_id}_{conversation.id}_{uuid.uuid4().hex[:8]}",
                "values": emb,
                "metadata": {
                    "user_id": str(conversation.user_id),
                    "conversation_id": str(conversation.id),
                    "text": chunk
                }
            } for chunk, emb in zip(batch, embeddings)]
            
            # Upsert in single batch
            await self._async_upsert(vectors)

    def _find_split_point(self, text: str, target_size: int) -> int:
        """Finds optimal split point considering sentence boundaries"""
        split_at = target_size
        for separator in ["\n\n", "\n", ". ", "! ", "? ", " "]:
            index = text.rfind(separator, 0, target_size + 1)
            if index > -1:
                split_at = index + len(separator)
                break
        return min(split_at, len(text))

    async def _async_upsert(self, vectors: List[Vector] | List[tuple] | List[dict]):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self.index.upsert(vectors=vectors))

    async def _get_embedding_and_upsert(self, chunk: str, user_id: str, conversation_id: str, vectors: list):
        """Process individual text chunks"""
        embedding = await self._get_embedding(chunk)
        vectors.append((
            f"{user_id}_{conversation_id}_{uuid.uuid4().hex[:8]}",  # Unique 8-char hash
            embedding,
            {
                "user_id": user_id,
                "conversation_id": conversation_id,
                "text": chunk
            }
        ))

    async def _get_embedding(self, text: str) -> list[float]:
        """Helper method to get OpenAI embeddings"""
        response = await self.openai_client.embeddings.create(
            input=text,
            model="text-embedding-ada-002"
        )
        return response.data[0].embedding
    
    async def _get_batch_embeddings(self, texts: list[str]) -> list[list[float]]:
        response = await self.openai_client.embeddings.create(
            input=texts,
            model="text-embedding-ada-002"
        )
        return [data.embedding for data in response.data]

    async def rag_search(self, query: str, user_id: str, conversation_id: str, top_k: int = 5):
        """
        Search Pinecone index with metadata filtering
        """
        # Generate query embedding
        query_embedding = await self._get_embedding(query)

        # Perform filtered search
        results = self.index.query(
            vector=query_embedding,
            filter={
                "user_id": str(user_id),
                "conversation_id": conversation_id
            },
            top_k=top_k,
            include_metadata=True
        )

        return results.to_dict()



def get_rag_service(mongo_service: Annotated[MongoService, Depends(get_mongo_service)], pdf_service: Annotated[PDFService, Depends(get_pdf_service)]):  # noqa: E501
    return RagService(mongo_service, pdf_service)
