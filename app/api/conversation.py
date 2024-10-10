from fastapi import APIRouter, Query
from models.conversation import Conversation
from odmantic import ObjectId
from services.mongo_service import MongoService, mongo_service

router = APIRouter(
    prefix="/conversations",
    tags=["Conversation"],
)


@router.get("")
async def get_conversations(user_id: str = Query(...), mongo_service: MongoService = mongo_service):
    if not user_id:
        return None
    return await mongo_service.engine.find(Conversation, Conversation.user_id == ObjectId(user_id))
    # print(conversations)
    # return None
