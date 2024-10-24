from typing import Optional

from fastapi import APIRouter, Query, Request, UploadFile
from services.rag_service import insert_to_rag, insert_to_rag_with_message
from services.document_and_inference_service import guideline_to_txt
from models.conversation import Conversation
from models.message import Message
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
    # print(conversation_id)
    id = ObjectId()
    file_id = mongo_service.fs.put(await file.read(), filename=file.filename, id=id)

    # If conversation_id is None, create a new conversation
    if not conversation_id or conversation_id == "null" or conversation_id == "undefined":
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
        # print(conversation)
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


@router.post("/pdf")
async def upload_pdf(
    file: UploadFile, request: Request, conversation_id: Optional[str] = Query(...), mongo_service: MongoService = mongo_service
):
    id = ObjectId()
    message_text = "A file has been uploaded, use the search text and document tool to access it using the next user prompt."

    file_id = mongo_service.fs.put(await file.read(), filename=file.filename, id=id)
    if not conversation_id or conversation_id == "null" or conversation_id == "undefined":
        new_conversation = Conversation(id=ObjectId(), user_id=ObjectId(request.state.user_id), contract_id=ObjectId(file_id))
        conversation = await mongo_service.engine.save(new_conversation)

        # Create a new message for the new conversation
        new_message = Message(
            id=ObjectId(),
            conversation_id=conversation.id,
            content=message_text,
            is_from_human=True,
            user_id=ObjectId(request.state.user_id),
        )
        await mongo_service.engine.save(new_message)
        await guideline_to_txt(mongo_service, ObjectId(file_id), str(conversation.id), new_message)
        await insert_to_rag_with_message(str(conversation.id), new_message, mongo_service)
        return {
            "message": "Contract uploaded",
            "file_id": str(file_id),
            "conversation_id": str(conversation.id),
        }
    else:
        conversation = await mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))
        if conversation:
            conversation.contract_id = ObjectId(file_id)
            await mongo_service.engine.save(conversation)

            # Create a new message for the existing conversation
            new_message = Message(
                id=ObjectId(),
                conversation_id=conversation.id,
                content=message_text,
                is_from_human=True,
                user_id=ObjectId(request.state.user_id),
            )

            await mongo_service.engine.save(new_message)
            await guideline_to_txt(mongo_service, ObjectId(file_id), str(conversation.id), new_message)
            await insert_to_rag_with_message(str(conversation.id), new_message, mongo_service)
            return {
                "message": "Contract uploaded",
                "file_id": str(file_id),
                "conversation_id": str(conversation.id),
            }
        else:
            return {"error": "Conversation not found"}
