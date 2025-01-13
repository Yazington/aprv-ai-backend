# app/services/conversation_service.py

from typing import Annotated, List, Optional
from fastapi import Depends
from odmantic import ObjectId

from app.config.logging_config import logger
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.mongo_service import MongoService, get_mongo_service


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
                user_id=ObjectId(user_id),
                thumbnail_text=content[:40]
            )
            return await self.mongo_service.engine.save(conversation)
        except Exception as e:
            logger.error(f"Error creating conversation for user {user_id}: {str(e)}")
            raise

    async def update_conversation(self, conversation_id: str, message: Message) -> Conversation:
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
            conversation = await self.mongo_service.engine.find_one(
                Conversation, 
                Conversation.id == ObjectId(conversation_id)
            )
            if not conversation:
                raise ValueError(f"Conversation not found with ID: {conversation_id}")
            conversation.thumbnail_text = message.content[:40]
            conversation.all_messages_ids.append(message.id)  # Already an ObjectId
            return await self.mongo_service.engine.save(conversation)
        except Exception as e:
            logger.error(f"Error updating conversation {conversation_id}: {str(e)}")
            raise

    async def get_conversations_by_user_id(self, user_id: str) -> Optional[List[Conversation]]:
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
            return await self.mongo_service.engine.find(
                Conversation,
                Conversation.user_id == ObjectId(user_id)
            )
        except Exception as e:
            logger.error(f"Error retrieving conversations for user {user_id}: {str(e)}")
            return None

    async def get_conversation_by_conversation_id(self, conversation_id: str) -> Optional[Conversation]:
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
            return await self.mongo_service.engine.find_one(
                Conversation,
                Conversation.id == ObjectId(conversation_id)
            )
        except Exception as e:
            logger.error(f"Error retrieving conversation {conversation_id}: {str(e)}")
            return None


def get_conversation_service(mongo_service: Annotated[MongoService, Depends(get_mongo_service)]):
    return ConversationService(mongo_service)
