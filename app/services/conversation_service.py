# app/services/conversation_service.py

from typing import Annotated

from fastapi import Depends
from beanie import PydanticObjectId

from app.config.logging_config import logger
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.mongo_service import MongoService, get_mongo_service


# Service class handling all conversation-related operations
# Manages creation, updating, and retrieval of conversations from MongoDB
class ConversationService:
    def __init__(self, mongo_service: MongoService):
        """Initialize conversation service with MongoDB service dependency"""
        self.mongo_service = mongo_service

    async def create_conversation(self, content: str, user_id: str) -> Conversation:
        """
        Create a new conversation with initial content for thumbnail
        Args:
            content: The content to use for the thumbnail
            user_id: String ID of the user creating the conversation
        Returns:
            The newly created Conversation object
        """
        try:
            conversation = Conversation(
                all_messages_ids=[],  # Will be updated when message is saved
                user_id=PydanticObjectId(user_id),
                thumbnail_text=content[:40]
            )
            return await conversation.save()
        except Exception as e:
            logger.error(f"Error creating conversation for user {user_id}: {str(e)}")
            raise

    async def update_conversation(self, conversation_id: str, message: Message):
        """
        Add a new message to an existing conversation and update its thumbnail text
        Args:
            conversation_id: String ID of the conversation to update
            message: New message to add to the conversation
        Returns:
            Updated Conversation object
        Raises:
            ValueError: If conversation with given ID is not found
        """
        try:
            conversation = await Conversation.find_one(Conversation.id == PydanticObjectId(conversation_id))
            if not conversation:
                raise ValueError(f"Conversation not found with ID: {conversation_id}")
            conversation.thumbnail_text = message.content[:40]
            conversation.all_messages_ids.append(message.id)  # Already a PydanticObjectId
            return await conversation.save()
        except Exception as e:
            logger.error(f"Error updating conversation {conversation_id}: {str(e)}")
            raise

    async def get_conversations_by_user_id(self, user_id: str):
        """
        Retrieve all conversations belonging to a specific user
        Args:
            user_id: String ID of the user whose conversations to retrieve
        Returns:
            List of Conversation objects or None if user_id is empty
        """
        if not user_id:
            return None
        try:
            return await Conversation.find(Conversation.user_id == PydanticObjectId(user_id)).to_list()
        except Exception as e:
            logger.error(f"Error retrieving conversations for user {user_id}: {str(e)}")
            return None

    async def get_conversation_by_conversation_id(self, conversation_id: str):
        """
        Retrieve a specific conversation by its ID
        Args:
            conversation_id: String ID of the conversation to retrieve
        Returns:
            Conversation object or None if conversation_id is empty or not found
        """
        if not conversation_id:
            return None
        try:
            return await Conversation.find_one(Conversation.id == PydanticObjectId(conversation_id))
        except Exception as e:
            logger.error(f"Error retrieving conversation {conversation_id}: {str(e)}")
            return None


# Dependency injection function for FastAPI to provide ConversationService instance
def get_conversation_service(mongo_service: Annotated[MongoService, Depends(get_mongo_service)]):
    return ConversationService(mongo_service)
