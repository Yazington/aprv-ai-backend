from typing import Optional

from fastapi import APIRouter, Request, UploadFile
from models.conversation import Conversation
from odmantic import ObjectId
from services.mongo_service import MongoService, mongo_service

router = APIRouter(
    prefix="/upload",
    tags=["Upload"],
)


@router.post("/image")
async def upload_image(
    file: UploadFile, request: Request, conversation_id: Optional[str] = None, mongo_service: MongoService = mongo_service
):
    try:
        # Upload the file to MongoDB
        file_id = await mongo_service.fs.put(await file.read(), filename=file.filename)

        # If conversation_id is None, create a new conversation
        if conversation_id is None:
            new_conversation = Conversation(id=ObjectId, all_messages_ids=[], user_id=ObjectId(request.state.user_id), files_ids=[file_id])
            conversation_id = await mongo_service.engine.save(new_conversation)
            return {
                "message": "Image uploaded and new conversation created",
                "file_id": str(file_id),
                "conversation_id": str(conversation_id),
            }

        # If conversation_id is provided, update the existing conversation
        else:
            conversation = await mongo_service.engine.find_one(Conversation, Conversation.id == conversation_id)
            if conversation:
                conversation.files_ids.append(file_id)
                # Append the new file_id to the existing file_ids list
                await mongo_service.engine.save(conversation)
                return {
                    "message": "Image uploaded and added to existing conversation",
                    "file_id": str(file_id),
                    "conversation_id": conversation_id,
                }
            else:
                return {"error": "Conversation not found"}

    except Exception as e:
        return {"error": str(e)}


@router.post("/pdf")
async def upload_pdf(
    file: UploadFile, request: Request, conversation_id: Optional[str] = None, mongo_service: MongoService = mongo_service
):
    try:
        file_id = await mongo_service.fs.put(await file.read(), filename=file.filename)

        # If conversation_id is None, create a new conversation
        if conversation_id is None:
            new_conversation = Conversation(id=ObjectId, all_messages_ids=[], user_id=ObjectId(request.state.user_id), files_ids=[file_id])
            conversation_id = await mongo_service.engine.save(new_conversation)
            return {
                "message": "Image uploaded and new conversation created",
                "file_id": str(file_id),
                "conversation_id": str(conversation_id),
            }

        # If conversation_id is provided, update the existing conversation
        else:
            conversation = await mongo_service.engine.find_one(Conversation, Conversation.id == conversation_id)
            if conversation:
                conversation.files_ids.append(file_id)
                # Append the new file_id to the existing file_ids list
                await mongo_service.engine.save(conversation)
                return {
                    "message": "Image uploaded and added to existing conversation",
                    "file_id": str(file_id),
                    "conversation_id": conversation_id,
                }
            else:
                return {"error": "Conversation not found"}

    except Exception as e:
        return {"error": str(e)}
