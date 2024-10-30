import asyncio
import os
import re
from typing import Annotated

import numpy as np
from fastapi import Depends
from lightrag import LightRAG, QueryParam  # type:ignore
from lightrag.utils import EmbeddingFunc
from lightrag.llm import gpt_4o_mini_complete, openai_embedding, openai_complete_if_cache  # type:ignore
from odmantic import ObjectId
from tenacity import retry, stop_after_attempt, wait_random_exponential

from app.config import settings
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.task import Task
from app.services.mongo_service import MongoService, get_mongo_service


class RagService:
    def __init__(self, mongo_service: MongoService):
        self.mongo_service = mongo_service

    @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
    async def search_text_and_documents(self, prompt: str, conversation_id: ObjectId, mode="hybrid") -> str:
        user_rag_workdir = "/app/data"
        safe_conversation_id = re.sub(r"[^a-zA-Z0-9_-]", "_", str(conversation_id))

        conversation = await self.mongo_service.engine.find_one(Conversation, Conversation.id == conversation_id)
        if not conversation:
            raise Exception("Conversation not found for id: " + str(conversation_id))
        os.makedirs(user_rag_workdir, exist_ok=True)

        conversation_dir = os.path.join(user_rag_workdir, safe_conversation_id)
        os.makedirs(conversation_dir, exist_ok=True)

        # rag = LightRAG(
        #     working_dir=conversation_dir,
        #     llm_model_func=gpt_4o_mini_complete,  # Use gpt_4o_mini_complete LLM model
        # )
        rag = LightRAG(
            working_dir=conversation_dir,
            llm_model_func=llm_model_func,
            embedding_func=EmbeddingFunc(embedding_dim=3072, max_token_size=8192, func=embedding_func),
        )

        try:
            response = await rag.aquery(prompt, param=QueryParam(mode=mode))
        except Exception as e:
            print(f"Error during query: {e}")
            return ""
        return response

    @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
    async def insert_to_rag(self, conversation_id: str):
        user_rag_workdir = "/app/data"

        # Sanitize conversation_id
        safe_conversation_id = re.sub(r"[^a-zA-Z0-9_-]", "_", conversation_id)

        conversation = await self.mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))
        if not conversation:
            raise Exception("Conversation not found for id: " + conversation_id)
        if not conversation.design_process_task_id:
            raise Exception("Task not found for conversation id: " + conversation_id)

        task = await self.mongo_service.engine.find_one(Task, Task.id == conversation.design_process_task_id)

        file_exists = self.mongo_service.fs.exists(task.generated_txt_id)
        if not file_exists:
            raise FileNotFoundError(f"File with ID {task.generated_txt_id} not found.")

        # Retrieve the file from GridFS
        processed_guideline_document_grid_out = self.mongo_service.fs.find_one(task.generated_txt_id)
        processed_guideline_document_txt = processed_guideline_document_grid_out.read().decode("utf-8")

        # Ensure /data and user directory exist
        os.makedirs(user_rag_workdir, exist_ok=True)

        user_dir = os.path.join(user_rag_workdir, safe_conversation_id)
        os.makedirs(user_dir, exist_ok=True)
        # rag = LightRAG(
        #     working_dir=user_dir,
        #     llm_model_func=gpt_4o_mini_complete,  # Use gpt_4o_mini_complete LLM model
        # )
        rag = LightRAG(
            working_dir=user_dir,
            llm_model_func=llm_model_func,
            embedding_func=EmbeddingFunc(embedding_dim=3072, max_token_size=8192, func=embedding_func),
        )

        await rag.ainsert(processed_guideline_document_txt)

    @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
    async def insert_to_rag_with_message(self, conversation_id: str, message: Message):
        user_rag_workdir = "/app/data"
        safe_conversation_id = re.sub(r"[^a-zA-Z0-9_-]", "_", conversation_id)

        conversation = await self.mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))
        if not conversation:
            raise Exception("Conversation not found for id: " + conversation_id)

        file_exists = self.mongo_service.fs.exists(message.uploaded_pdf_id)
        if not file_exists:
            raise FileNotFoundError(f"File with ID {message.uploaded_pdf_id} not found.")

        processed_guideline_document_grid_out = self.mongo_service.fs.find_one(message.uploaded_pdf_id)
        processed_guideline_document_txt = processed_guideline_document_grid_out.read().decode("utf-8")
        os.makedirs(user_rag_workdir, exist_ok=True)

        user_dir = os.path.join(user_rag_workdir, safe_conversation_id)
        os.makedirs(user_dir, exist_ok=True)
        print("type: ", type(processed_guideline_document_txt))

        # rag = LightRAG(
        #     working_dir=user_dir,
        #     llm_model_func=gpt_4o_mini_complete,  # Use gpt_4o_mini_complete LLM model
        # )
        rag = LightRAG(
            working_dir=user_dir,
            llm_model_func=llm_model_func,
            embedding_func=EmbeddingFunc(embedding_dim=3072, max_token_size=8192, func=embedding_func),
        )

        # Split the document into smaller chunks
        # document_chunks = self.split_document_into_chunks(processed_guideline_document_txt)

        await rag.ainsert(processed_guideline_document_txt)

    def split_document_into_chunks(self, document: str, chunk_size: int = 10000) -> list:
        """
        Splits a document into chunks based on the specified chunk size.
        You can adjust `chunk_size` as needed for your application.
        """
        # This is a simple example. Modify it based on actual requirements.
        return [document[i : i + chunk_size] for i in range(0, len(document), chunk_size)]

    # async def embedding_func(self, texts: list[str]) -> np.ndarray:
    #     return await openai_embedding(texts, model="text-embedding-3-large", api_key=settings.settings.openai_api_key)


async def llm_model_func(prompt, system_prompt=None, history_messages=[], **kwargs) -> str:
    return await openai_complete_if_cache(
        "gpt-4o-mini",
        prompt,
        system_prompt=system_prompt,
        history_messages=history_messages,
        api_key=settings.settings.openai_api_key,
        **kwargs,
    )


# Embedding function


async def embedding_func(texts: list[str]) -> np.ndarray:
    return await openai_embedding(
        texts,
        model="text-embedding-3-large",
        api_key=settings.settings.openai_api_key,
    )


def get_rag_service(mongo_service: Annotated[MongoService, Depends(get_mongo_service)]):
    return RagService(mongo_service)
