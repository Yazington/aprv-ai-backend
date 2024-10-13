import logging
from typing import Optional

from fastapi import APIRouter, Query, Request, UploadFile
from models.conversation import Conversation
from odmantic import ObjectId
from services.mongo_service import MongoService, mongo_service

router = APIRouter(
    prefix="/upload",
    tags=["Upload"],
)


@router.post("/image")
async def upload_image(
    file: UploadFile, request: Request, conversation_id: Optional[str] = Query(...), mongo_service: MongoService = mongo_service
):
    try:
        id = ObjectId()
        file_id = mongo_service.fs.put(await file.read(), filename=file.filename, id=id)

        # If conversation_id is None, create a new conversation
        if not conversation_id or conversation_id == "null":
            new_conversation = Conversation(id=ObjectId(), design_id=ObjectId(file_id), user_id=ObjectId(request.state.user_id))
            conversation = await mongo_service.engine.save(new_conversation)
            return {
                "message": "Image uploaded and new conversation created",
                "file_id": str(file_id),
                "conversation_id": str(conversation.id),
            }

        # If conversation_id is provided, update the existing conversation
        else:
            conversation = await mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))
            print(conversation)
            if conversation:
                conversation.design_id = ObjectId(file_id)
                # Append the new file_id to the existing file_ids list
                await mongo_service.engine.save(conversation)
                return {
                    "message": "Image uploaded and added to existing conversation",
                    "file_id": str(file_id),
                    "conversation_id": str(conversation.id),
                }
            else:
                return {"error": "Conversation not found"}

    except Exception as e:
        return {"error": str(e)}


@router.post("/pdf")
async def upload_pdf(
    file: UploadFile, request: Request, conversation_id: Optional[str] = Query(...), mongo_service: MongoService = mongo_service
):
    id = ObjectId()
    file_id = mongo_service.fs.put(await file.read(), filename=file.filename, id=id)
    if not conversation_id or conversation_id == "null":
        new_conversation = Conversation(id=ObjectId(), user_id=ObjectId(request.state.user_id), contract_id=ObjectId(file_id))
        conversation = await mongo_service.engine.save(new_conversation)
        return {
            "message": "Image uploaded and new conversation created",
            "file_id": str(file_id),
            "conversation_id": str(conversation.id),
        }
    else:
        conversation = await mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))
        print(conversation)
        if conversation:
            conversation.contract_id = ObjectId(file_id)
            await mongo_service.engine.save(conversation)
            return {
                "message": "Image uploaded and added to existing conversation",
                "file_id": str(file_id),
                "conversation_id": str(conversation.id),
            }
        else:
            return {"error": "Conversation not found"}
