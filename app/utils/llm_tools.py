import os
import re
from typing import Annotated, Any, List

from fastapi import Depends
from odmantic import ObjectId
from openai.types.chat import ChatCompletionToolParam
from tenacity import retry, stop_after_attempt, wait_random_exponential

from app.models.conversation import Conversation
from app.models.review import Review
from app.models.task import Task
from app.services.mongo_service import MongoService, get_mongo_service
from app.services.rag_service import RagService, get_rag_service


class LLMToolsService:
    """Service providing various LLM-related tools and utilities for conversation processing.

    This service handles operations like semantic text search, file checking, and review retrieval
    for conversations between assistants and licensees/licensors."""

    AVAILABLE_TOOLS: list[ChatCompletionToolParam] = [
        {
            "type": "function",
            "function": {
                "name": "find_information_in_document_of_conversation",
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

    def __init__(self, mongo_service: MongoService, rag_service: RagService):
        """Initialize the LLM tools service with MongoDB connection.

        Args:
            mongo_service: MongoDB service instance for database operations
            rag_service: RAG service instance for semantic search operations"""
        self.mongo_service = mongo_service
        self.rag_service = rag_service

    @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
    async def find_information_in_document_of_conversation(self, prompt: str, conversation_id: str) -> str:
        """Perform semantic text search using RAG (Retrieval-Augmented Generation) on conversation data.

        Args:
            prompt: The query text to search for
            conversation_id: ID of the conversation to search within

        Returns:
            str: The most relevant text found, or empty string if no results"""
        try:
            # Use RagService to search for similar content
            results: List[str] = await self.rag_service.search_similar(prompt, conversation_id)
            # Join the results with newlines if multiple chunks are returned
            return "\n".join(results) if results else ""
        except Exception as e:
            print(f"Error during RAG search: {e}")
            return ""

    async def check_for_conversation_uploaded_design_file(self, conversation_id):
        """Check if a design file has been uploaded for the given conversation.

        Args:
            conversation_id: ID of the conversation to check

        Returns:
            str|None: Design file ID if found, None otherwise"""
        conversation = await self.mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))
        if not conversation or not conversation.design_id:
            return None
        return conversation.design_id

    async def check_for_conversation_uploaded_guidelines_file(self, conversation_id):
        """Check if a guidelines file has been uploaded for the given conversation.

        Args:
            conversation_id: ID of the conversation to check

        Returns:
            str|None: Guidelines file ID if found, None otherwise"""
        conversation = await self.mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))
        if not conversation or not conversation.guidelines_id:
            return None
        return conversation.guidelines_id

    async def check_for_conversation_review_or_approval_process_file(self, conversation_id):
        """Check if a review/approval process file exists for the conversation.

        Args:
            conversation_id: ID of the conversation to check

        Returns:
            str|None: Review file ID if found, None otherwise"""
        conversation = await self.mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))
        if not conversation or not conversation.design_process_task_id:
            return None
        task = await self.mongo_service.engine.find_one(Task, Task.id == conversation.design_process_task_id)
        if not task:
            return None
        return task.generated_txt_id

    async def get_guidelines_page_review(self, conversation_id, page_number):
        """Retrieve the review of a design against a specific guidelines page.

        Args:
            conversation_id: ID of the conversation to check
            page_number: The page number to get review for

        Returns:
            Review|None: Review object if found, None otherwise"""
        review_at_given_page = await self.mongo_service.engine.find_one(
            Review, Review.conversation_id == conversation_id and Review.page_number == page_number
        )
        if not review_at_given_page:
            return None
        return review_at_given_page


def get_llm_tools_service(
    mongo_service: Annotated[MongoService, Depends(get_mongo_service)], rag_service: Annotated[RagService, Depends(get_rag_service)]
):
    """Dependency injection function to get an instance of LLMToolsService.

    Args:
        mongo_service: MongoDB service instance

    Returns:
        LLMToolsService: Initialized LLM tools service instance"""
    return LLMToolsService(mongo_service, rag_service)
