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
        message = Message(
            id=ObjectId(),
            conversation_id=conversation_id,
            content=content,
            is_from_human=True,
            user_id=user_id,
        )
        return await self.mongo_service.engine.save(message)

    async def retrieve_message_by_id(self, message_id: ObjectId) -> Optional[Message]:
        return await self.mongo_service.engine.find_one(Message, Message.id == message_id)

    async def retrieve_message_history(self, conversation_id: ObjectId, exclude_message_id: ObjectId) -> str:
        if conversation_id:
            past_messages = await self.mongo_service.engine.find(
                Message,
                Message.conversation_id == conversation_id,
                sort=asc(Message.created_at),
            )
            past_messages = [msg for msg in past_messages if msg.id != exclude_message_id]
            return "\n".join(msg.content for msg in past_messages)
        return ""

    def get_tokenized_message_count(self, message: str) -> int:
        return count_tokens(message)


def get_message_service(mongo_service: Annotated[MongoService, Depends(get_mongo_service)]):
    return MessageService(mongo_service)
