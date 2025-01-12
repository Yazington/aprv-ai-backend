import os
from typing import Annotated, List, Optional, Dict, Any
from app.models.task import Task
from fastapi import Depends
from odmantic import ObjectId
from openai import AsyncOpenAI
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.mongo_service import MongoService, get_mongo_service
from app.config.settings import settings
from app.config.logging_config import logger
from PyPDF2 import PdfReader
from io import BytesIO


class RagService:
    def __init__(self, mongo_service: MongoService):
        """Initialize RAG service with MongoDB connection"""
        self.mongo_service = mongo_service
        self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def initialize(self):
        """Initialize basic index for conversation_id"""
        try:
            db = self.mongo_service.engine.client.get_database("aprvai")
            # Create compound index for conversation_id and source_file
            await db.embeddings.create_index([("conversation_id", 1), ("source_file", 1)])
        except Exception as e:
            logger.error(f"Index creation error (might already exist): {e}")

    async def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings from OpenAI API"""
        response = await self.openai_client.embeddings.create(model="text-embedding-3-small", input=texts)
        return [embedding.embedding for embedding in response.data]

    def _extract_text_from_pdf(self, pdf_bytes: bytes) -> str:
        """Extract text content from PDF bytes."""
        try:
            pdf_file = BytesIO(pdf_bytes)
            pdf_reader = PdfReader(pdf_file)
            text_content = []

            for page in pdf_reader.pages:
                text_content.append(page.extract_text())

            return "\n".join(text_content)
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            raise

    async def insert_to_rag(self, conversation_id: str) -> None:
        """Insert conversation data into RAG system"""
        conversation = await self.mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))
        if not conversation or not conversation.design_process_task_id:
            raise Exception(f"Conversation or task not found for id: {conversation_id}")

        task = await self.mongo_service.engine.find_one(Task, Task.id == conversation.design_process_task_id)
        if not task or not task.generated_txt_id:
            raise Exception("Task or generated text not found")

        # Get document from GridFS
        grid_out = self.mongo_service.fs.find_one(task.generated_txt_id)
        if not grid_out:
            raise FileNotFoundError(f"File with ID {task.generated_txt_id} not found")

        document_text = grid_out.read().decode("utf-8")
        chunks = self.split_document_into_chunks(document_text)

        # Get embeddings for chunks
        embeddings = await self._get_embeddings(chunks)

        # Add chunks to MongoDB
        documents = [
            {
                "conversation_id": conversation_id,
                "text": chunk,
                "embedding": embedding,
                "source_file": str(task.generated_txt_id),
                "source_type": "task",
            }
            for chunk, embedding in zip(chunks, embeddings)
        ]

        await self.mongo_service.engine.client.get_database("aprvai").embeddings.insert_many(documents)

    async def insert_to_rag_with_message(self, conversation_id: str, message: Message) -> None:
        """Insert message data into RAG system"""
        if not message.uploaded_pdf_ids:
            raise Exception("No PDF IDs found in message")

        all_documents = []
        processed_files = 0
        total_chunks = 0

        # Process each PDF file
        for pdf_id in message.uploaded_pdf_ids:
            grid_out = self.mongo_service.fs.find_one(pdf_id)
            if not grid_out:
                logger.warning(f"File with ID {pdf_id} not found, skipping")
                continue

            try:
                # Read PDF content
                pdf_bytes = grid_out.read()
                filename = grid_out.filename
                logger.info(f"Processing PDF {filename} ({len(pdf_bytes) / 1024:.2f}KB)")

                # Extract text from PDF
                document_text = self._extract_text_from_pdf(pdf_bytes)
                logger.info(f"Extracted {len(document_text)} characters of text from {filename}")

                # Split into chunks and get embeddings
                chunks = self.split_document_into_chunks(document_text)
                logger.info(f"Split {filename} into {len(chunks)} chunks")

                embeddings = await self._get_embeddings(chunks)
                logger.info(f"Generated embeddings for {len(embeddings)} chunks from {filename}")

                # Create documents for this PDF
                pdf_documents = [
                    {
                        "conversation_id": conversation_id,
                        "message_id": str(message.id),
                        "text": chunk,
                        "embedding": embedding,
                        "source_file": str(pdf_id),
                        "source_filename": filename,
                        "chunk_index": idx,
                        "total_chunks": len(chunks),
                    }
                    for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings))
                ]

                all_documents.extend(pdf_documents)
                total_chunks += len(chunks)
                processed_files += 1

            except Exception as e:
                logger.error(f"Error processing file {pdf_id}: {str(e)}")
                continue

        if not all_documents:
            raise Exception("No valid content found in any of the PDF files")

        # Add all chunks to MongoDB
        await self.mongo_service.engine.client.get_database("aprvai").embeddings.insert_many(all_documents)
        logger.info(f"Added {total_chunks} chunks from {processed_files} files to RAG system")

    async def search_similar(self, query: str, conversation_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for similar content in the RAG system
        Returns the most relevant text chunks with source information
        """
        # Get query embedding
        query_embedding = await self._get_embeddings([query])

        try:
            # For now, just return the most recent chunks since we can't do vector search without Atlas
            results = (
                await self.mongo_service.engine.client.get_database("aprvai")
                .embeddings.find(
                    {"conversation_id": conversation_id},
                    {"text": 1, "source_filename": 1, "source_file": 1, "chunk_index": 1, "total_chunks": 1, "_id": 0},
                )
                .limit(limit)
                .to_list(length=limit)
            )

            # Format results with source information
            formatted_results = []
            for doc in results or []:
                result = {
                    "text": doc["text"],
                    "source": doc.get("source_filename", "Unknown"),
                    "file_id": doc.get("source_file", "Unknown"),
                }
                if "chunk_index" in doc and "total_chunks" in doc:
                    result["position"] = f"Part {doc['chunk_index'] + 1} of {doc['total_chunks']}"
                formatted_results.append(result)

            return formatted_results

        except Exception as e:
            logger.error(f"Error during similarity search: {e}")
            return []

    def split_document_into_chunks(self, document: str, chunk_size: int = 500) -> List[str]:
        """Split document into smaller chunks, using sentence boundaries where possible"""
        sentences = document.split(". ")
        chunks = []
        current_chunk = []
        current_size = 0

        for sentence in sentences:
            sentence_size = len(sentence.split())
            if current_size + sentence_size > chunk_size and current_chunk:
                chunks.append(". ".join(current_chunk) + ".")
                current_chunk = []
                current_size = 0
            current_chunk.append(sentence)
            current_size += sentence_size

        if current_chunk:
            chunks.append(". ".join(current_chunk) + ".")

        return chunks


async def get_rag_service(mongo_service: Annotated[MongoService, Depends(get_mongo_service)]) -> RagService:
    """Dependency injection function to get RAG service instance"""
    service = RagService(mongo_service)
    await service.initialize()
    return service
