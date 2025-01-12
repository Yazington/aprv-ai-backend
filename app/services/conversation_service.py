# app/services/conversation_service.py

from typing import Annotated

from fastapi import Depends
from odmantic import ObjectId

from app.models.conversation import Conversation
from app.models.message import Message
from app.services.mongo_service import MongoService, get_mongo_service


# Service class handling all conversation-related operations
# Manages creation, updating, and retrieval of conversations from MongoDB
class ConversationService:
    def __init__(self, mongo_service: MongoService):
        """Initialize conversation service with MongoDB service dependency"""
        self.mongo_service = mongo_service

    async def create_conversation(self, message: Message, user_id: ObjectId) -> Conversation:
        """
        Create a new conversation with an initial message
        Args:
            message: The first message in the conversation
            user_id: ID of the user creating the conversation
        Returns:
            The newly created Conversation object
        """
        conversation = Conversation(id=ObjectId(), all_messages_ids=[message.id], user_id=user_id, thumbnail_text=message.content[:40])
        return await self.mongo_service.engine.save(conversation)

    async def update_conversation(self, conversation_id: ObjectId, message: Message):
        """
        Add a new message to an existing conversation and update its thumbnail text
        Args:
            conversation_id: ID of the conversation to update
            message: New message to add to the conversation
        Returns:
            Updated Conversation object
        Raises:
            ValueError: If conversation with given ID is not found
        """
        conversation = await self.mongo_service.engine.find_one(Conversation, Conversation.id == conversation_id)
        if not conversation:
            raise ValueError("Conversation not found")
        conversation.thumbnail_text = message.content[:40]
        conversation.all_messages_ids.append(message.id)
        return await self.mongo_service.engine.save(conversation)

    async def get_conversations_by_user_id(self, user_id: str):
        """
        Retrieve all conversations belonging to a specific user
        Args:
            user_id: ID of the user whose conversations to retrieve
        Returns:
            List of Conversation objects or None if user_id is empty
        """
        if not user_id:
            return None
        return await self.mongo_service.engine.find(Conversation, Conversation.user_id == ObjectId(user_id))

    async def get_conversation_by_conversation_id(self, conversation_id: str):
        """
        Retrieve a specific conversation by its ID
        Args:
            conversation_id: ID of the conversation to retrieve
        Returns:
            Conversation object or None if conversation_id is empty
        """
        if not conversation_id:
            return None
        return await self.mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))


# Dependency injection function for FastAPI to provide ConversationService instance
def get_conversation_service(mongo_service: Annotated[MongoService, Depends(get_mongo_service)]):
    return ConversationService(mongo_service)
