# app/services/message_service.py

from typing import Annotated, Optional

from fastapi import Depends
from odmantic import ObjectId
from odmantic.query import asc

from app.models.message import Message
from app.services.mongo_service import MongoService, get_mongo_service
from app.utils.tiktoken import count_tokens


class MessageService:
    def __init__(self, mongo_service: MongoService):
        self.mongo_service = mongo_service

    async def create_message(self, content: str, conversation_id: ObjectId, user_id: ObjectId) -> Message:
        """Creates and saves a new message in the database.

        Args:
            content: The text content of the message
            conversation_id: ID of the conversation this message belongs to
            user_id: ID of the user who sent the message

        Returns:
            The created Message object with a new ObjectId
        """
        message = Message(
            id=ObjectId(),
            conversation_id=conversation_id,
            content=content,
            is_from_human=True,
            user_id=user_id,
        )
        return await self.mongo_service.engine.save(message)

    async def retrieve_message_by_id(self, message_id: ObjectId) -> Optional[Message]:
        """Retrieves a single message by its ID.

        Args:
            message_id: The ID of the message to retrieve

        Returns:
            The Message object if found, None otherwise
        """
        return await self.mongo_service.engine.find_one(Message, Message.id == message_id)

    async def retrieve_message_history(self, conversation_id: ObjectId, exclude_message_id: ObjectId) -> str:
        """Retrieves the message history for a conversation, excluding a specific message.

        Args:
            conversation_id: ID of the conversation to get history for
            exclude_message_id: ID of message to exclude from history

        Returns:
            A string containing all message contents joined by newlines,
            or empty string if no conversation_id provided
        """
        if conversation_id:
            past_messages = await self.mongo_service.engine.find(
                Message,
                Message.conversation_id == conversation_id,
                sort=asc(Message.created_at),
            )
            past_messages = [msg for msg in past_messages if msg.id != exclude_message_id]
            return "\n".join(msg.content for msg in past_messages)
        return ""

    async def get_conversations_messages(self, conversation_id: str):
        """Retrieves all messages for a given conversation.

        Args:
            conversation_id: String ID of the conversation

        Returns:
            List of Message objects for the conversation,
            or None if no conversation_id provided
        """
        if not conversation_id:
            return None
        return await self.mongo_service.engine.find(Message, Message.conversation_id == ObjectId(conversation_id))

    def get_tokenized_message_count(self, message: str) -> int:
        """Counts the number of tokens in a message using tiktoken.

        Args:
            message: The message text to count tokens for

        Returns:
            Integer count of tokens in the message
        """
        return count_tokens(message)


def get_message_service(mongo_service: Annotated[MongoService, Depends(get_mongo_service)]):
    return MessageService(mongo_service)
