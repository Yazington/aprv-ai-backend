# app/services/message_service.py

from typing import Annotated, Optional

from fastapi import Depends
from beanie import PydanticObjectId
from odmantic.query import asc

from app.config.logging_config import logger
from app.models.message import Message
from app.services.mongo_service import MongoService, get_mongo_service
from app.utils.tiktoken import count_tokens


class MessageService:
    def __init__(self, mongo_service: MongoService):
        self.mongo_service = mongo_service

    async def create_message(self, content: str, conversation_id: str, user_id: str) -> Message:
        """Creates and saves a new message in the database.

        Args:
            content: The text content of the message
            conversation_id: String ID of the conversation this message belongs to
            user_id: String ID of the user who sent the message

        Returns:
            The created Message object
        """
        try:
            message = Message(
                conversation_id=PydanticObjectId(conversation_id),
                content=content,
                is_from_human=True,
                user_id=user_id,
            )
            return await message.save()
        except Exception as e:
            logger.error(f"Error creating message: {str(e)}")
            raise

    async def retrieve_message_by_id(self, message_id: str) -> Optional[Message]:
        """Retrieves a single message by its ID.

        Args:
            message_id: The string ID of the message to retrieve

        Returns:
            The Message object if found, None otherwise
        """
        try:
            logger.info(f"Attempting to retrieve message with ID: {message_id}")
            message = await Message.get(PydanticObjectId(message_id))
            if message:
                logger.info(f"Found message: {message.id}, conversation_id: {message.conversation_id}")
            else:
                logger.warning(f"No message found with ID: {message_id}")
            return message
        except Exception as e:
            logger.error(f"Error retrieving message by ID {message_id}: {str(e)}")
            return None

    async def retrieve_message_history(self, conversation_id: str, exclude_message_id: str) -> str:
        """Retrieves the message history for a conversation, excluding a specific message.

        Args:
            conversation_id: String ID of the conversation to get history for
            exclude_message_id: String ID of message to exclude from history

        Returns:
            A string containing all message contents joined by newlines,
            or empty string if no conversation_id provided
        """
        if conversation_id:
            try:
                past_messages = await Message.find(
                    Message.conversation_id == PydanticObjectId(conversation_id),
                ).sort("+created_at").to_list()
                past_messages = [msg for msg in past_messages if str(msg.id) != exclude_message_id]
                return "\n".join(msg.content for msg in past_messages)
            except Exception as e:
                logger.error(f"Error retrieving message history: {str(e)}")
                return ""
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
        try:
            return await Message.find(
                Message.conversation_id == PydanticObjectId(conversation_id)
            ).sort("+created_at").to_list()
        except Exception as e:
            logger.error(f"Error retrieving conversation messages: {str(e)}")
            return None

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
