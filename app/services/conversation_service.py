# app/services/conversation_service.py

from typing import Annotated

from fastapi import Depends
from odmantic import ObjectId

from app.models.conversation import Conversation
from app.models.message import Message
from app.services.mongo_service import MongoService, get_mongo_service


class ConversationService:
    def __init__(self, mongo_service: MongoService):
        self.mongo_service = mongo_service

    async def create_conversation(self, message: Message, user_id: ObjectId) -> Conversation:
        conversation = Conversation(id=ObjectId(), all_messages_ids=[message.id], user_id=user_id, thumbnail_text=message.content[:40])
        return await self.mongo_service.engine.save(conversation)

    async def update_conversation(self, conversation_id: ObjectId, message: Message):
        conversation = await self.mongo_service.engine.find_one(Conversation, Conversation.id == conversation_id)
        if not conversation:
            raise ValueError("Conversation not found")
        conversation.thumbnail_text = message.content[:40]
        conversation.all_messages_ids.append(message.id)
        return await self.mongo_service.engine.save(conversation)

    async def get_conversations_by_user_id(self, user_id: str):
        if not user_id:
            return None
        return await self.mongo_service.engine.find(Conversation, Conversation.user_id == ObjectId(user_id))

    async def get_conversation_by_conversation_id(self, conversation_id: str):
        if not conversation_id:
            return None
        return await self.mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))


def get_conversation_service(mongo_service: Annotated[MongoService, Depends(get_mongo_service)]):
    return ConversationService(mongo_service)
