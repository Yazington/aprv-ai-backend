

import os
import re
from typing import Annotated, Any

from fastapi import Depends
from lightrag import LightRAG, QueryParam  # type:ignore
from lightrag.llm import gpt_4o_mini_complete  # type:ignore
from odmantic import ObjectId
from tenacity import retry, stop_after_attempt, wait_random_exponential

from app.models.conversation import Conversation
from app.models.review import Review
from app.models.task import Task
from app.services.mongo_service import MongoService, get_mongo_service


class LLMToolsService:
    AVAILABLE_TOOLS: list[dict[str, Any]] = [
            {
                "type": "function",
                "function": {
                    "name": "search_similar_text",
                    "description": """Does semantic text search with graph based RAG on a concatenated guidelines file or extensive review
                    of the design against each pages and finds the text that matches it best.
                    It does this for the current conversation between the assistant and
                    the brand licensee/licensor.""",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "prompt": {
                                "type": "string",
                                "description": """The prompt or query text for which RAG results are needed.
                                If user needs to know what is in it, summarize it""",
                            },
                            "conversation_id": {
                                "type": "string",
                                "description": """The id of the current conversation happening between the assistant and the licensee/licensor""",
                            },
                        },
                        "required": ["prompt", "conversation_id"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_for_conversation_uploaded_design_file",
                    "description": """Checks wether there is an uploaded design file and returns design file id if it found it.
                    Otherwise it returns None. Use get_current_conversation_id to get the conversation_id!!!!!""",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "conversation_id": {
                                "type": "string",
                                "description": """The id of the current conversation happening between the assistant and the licensee/licensor.
                                The conversation_id comes from the tool get_current_conversation_id""",
                            },
                        },
                        "required": ["conversation_id"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_for_conversation_uploaded_guidelines_file",
                    "description": """Checks wether there is an uploaded guidelines file and returns guidelines file id if it found it.
                    Otherwise it returns None. Use get_current_conversation_id to get the conversation_id!!!!! """,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "conversation_id": {
                                "type": "string",
                                "description": """The id of the current conversation happening between the assistant and the licensee/licensor. The conversation_id comes from the tool get_current_conversation_id""",
                            },
                        },
                        "required": ["conversation_id"],
                        "additionalProperties": False,
                    },
                },
            },
            # {
            #     "type": "function",
            #     "function": {
            #         "name": "get_current_conversation_id",
            #         "description": """Gets the current ongoing conversation_id between the assistant and the licensee/licensor. The conversation_id comes from this tool.""",
            #         "parameters": {
            #             "type": "object",
            #             "properties": {
            #             },
            #             "required": [],
            #             "additionalProperties": False,
            #         },
            #     },
            # },
            {
                "type": "function",
                "function": {
                    "name": "check_for_conversation_review_or_approval_process_file",
                    "description": """A file might have been uploaded containing the review of the design against all guidelines pages.
                    If the file exists, we return it it's id. Otherwise we return None.
                    The review processed is started by the licensee/licensor (they have to click on Full Compliance Check)!""",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "conversation_id": {
                                "type": "string",
                                "description": """The id of the current conversation happening between the assistant and the licensee/licensor""",
                            },
                        },
                        "required": ["conversation_id"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_guidelines_page_review",
                    "description": """Gets the review of the design against a page of the guidelines file if and only if the review has happened.
                    The review processed is started by the licensee/licensor (they have to click on Full Compliance Check)""",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "conversation_id": {
                                "type": "string",
                                "description": """The id of the current conversation happening between the assistant and the licensee/licensor""",
                            },
                            "page_number": {
                                "type": "integer",
                                "description": """The page number is used to get the review of the design against a guidelines file page""",
                            },
                        },
                        "required": ["conversation_id", "page_number"],
                        "additionalProperties": False,
                    },
                },
            },
        ]

    def __init__(self, mongo_service: MongoService):
        self.mongo_service = mongo_service


    @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
    async def search_similar_text(self, prompt: str, conversation_id: str) -> str:
        user_rag_workdir = "./data"
        safe_conversation_id = re.sub(r"[^a-zA-Z0-9_-]", "_", conversation_id)

        conversation = await self.mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))
        if not conversation:
            raise Exception("Conversation not found for id: " + conversation_id)
        os.makedirs(user_rag_workdir, exist_ok=True)

        conversation_dir = os.path.join(user_rag_workdir, safe_conversation_id)
        os.makedirs(conversation_dir, exist_ok=True)

        rag = LightRAG(
            working_dir=conversation_dir,
            llm_model_func=gpt_4o_mini_complete,  # Use gpt_4o_mini_complete LLM model
        )

        try:
            response = await rag.aquery(prompt, param=QueryParam(mode="hybrid"))
        except Exception as e:
            print(f"Error during query: {e}")
            return ""
        return response

    async def check_for_conversation_uploaded_design_file(self,conversation_id):
        conversation =  await self.mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))
        if not conversation.design_id:
            return None
        return conversation.design_id

    async def check_for_conversation_uploaded_guidelines_file(self, conversation_id):
        conversation =  await self.mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))
        if not conversation.guidelines_id:
            return None
        return conversation.guidelines_id

    async def check_for_conversation_review_or_approval_process_file(self, conversation_id):
        conversation =  await self.mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))
        if not conversation.design_process_task_id:
            return None
        task = await self.mongo_service.engine.find_one(Task, Task.id == conversation.design_process_task_id)
        if not task:
            return None
        return task.generated_txt_id

    async def get_guidelines_page_review(self, conversation_id, page_number):
        review_at_given_page = await self.mongo_service.engine.find_one(Review, Review.conversation_id == conversation_id and Review.page_number == page_number)
        if not review_at_given_page:
            return None
        return review_at_given_page

def get_llm_tools_service(mongo_service: Annotated[MongoService, Depends(get_mongo_service)]):
    return LLMToolsService(mongo_service)
