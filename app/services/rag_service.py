import asyncio
import os
import re
from typing import List

from exceptions.bad_conversation_files import DesignOrGuidelineNotFoundError
from lightrag import LightRAG, QueryParam  # type:ignore
from lightrag.llm import gpt_4o_complete, gpt_4o_mini_complete  # type:ignore
from models.conversation import Conversation
from models.task import Task
from odmantic import ObjectId
from services.mongo_service import MongoService


async def get_rag_results(prompt: str, conversation_id: ObjectId, mongo_service: MongoService, mode="global") -> str:
    user_rag_workdir = "./data"

    # Sanitize conversation_id
    safe_conversation_id = re.sub(r"[^a-zA-Z0-9_-]", "_", str(conversation_id))

    conversation = await mongo_service.engine.find_one(Conversation, Conversation.id == conversation_id)
    if not conversation:
        raise Exception("Conversation not found for id: " + str(conversation_id))
    if not conversation.contract_id or not conversation.design_id:
        return ""

    # Ensure /data and conversation directory exist
    os.makedirs(user_rag_workdir, exist_ok=True)

    conversation_dir = os.path.join(user_rag_workdir, safe_conversation_id)
    os.makedirs(conversation_dir, exist_ok=True)

    # Initialize LightRAG with the user's working directory
    rag = LightRAG(
        working_dir=conversation_dir,
        llm_model_func=gpt_4o_mini_complete,  # Use gpt_4o_mini_complete LLM model
    )

    # Run the blocking `rag.query` in a separate thread and wait for it to finish
    try:
        response = await asyncio.to_thread(rag.query, prompt, param=QueryParam(mode=mode))
    except Exception as e:
        print(f"Error during query: {e}")
        return ""

    return response


async def insert_user_data(conversation_id: str, mongo_service: MongoService):
    user_rag_workdir = "./data"

    # Sanitize conversation_id
    safe_conversation_id = re.sub(r"[^a-zA-Z0-9_-]", "_", conversation_id)

    conversation = await mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))
    if not conversation:
        raise Exception("Conversation not found for id: " + conversation_id)
    if not conversation.design_process_task_id:
        raise Exception("Task not found for conversation id: " + conversation_id)

    task = await mongo_service.engine.find_one(Task, Task.id == conversation.design_process_task_id)

    # Check if the file exists in GridFS
    file_exists = mongo_service.fs.exists(task.generated_txt_id)
    if not file_exists:
        raise FileNotFoundError(f"File with ID {task.generated_txt_id} not found.")

    # Retrieve the file from GridFS
    processed_guideline_document_grid_out = mongo_service.fs.get(task.generated_txt_id)
    processed_guideline_document_txt = processed_guideline_document_grid_out.read().decode("utf-8")  # Assuming the file contains text data

    # Ensure /data and user directory exist
    os.makedirs(user_rag_workdir, exist_ok=True)

    user_dir = os.path.join(user_rag_workdir, safe_conversation_id)
    os.makedirs(user_dir, exist_ok=True)

    # Initialize LightRAG with the user's working directory
    rag = LightRAG(
        working_dir=user_dir,
        llm_model_func=gpt_4o_mini_complete,
    )

    # Run the blocking `rag.insert` in a separate thread and wait for it to finish
    try:
        await asyncio.to_thread(rag.insert, processed_guideline_document_txt)
        print(f"Data inserted successfully for user {conversation_id}.")
    except Exception as e:
        print(f"Error during data insertion for user {conversation_id}: {e}")
        raise
