from typing import Annotated, Optional

# from memory_profiler import profile  # type: ignore
from fastapi import APIRouter, Depends, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from odmantic import ObjectId

from app.config.logging_config import logger
from app.models.conversation import Conversation
from app.models.files import File, FileResponse
from app.models.message import Message
from app.services.mongo_service import MongoService, get_mongo_service
from app.services.rag_service import RagService, get_rag_service
from app.services.upload_service import UploadService, get_upload_service

router = APIRouter(
    prefix="/upload",
    tags=["Upload"],
)


@router.post("/image")
async def upload_image(
    file: UploadFile,
    request: Request,
    mongo_service: Annotated[MongoService, Depends(get_mongo_service)],
    conversation_id: Optional[str] = Query(None),
):

    # print(conversation_id)
    id = ObjectId()
    file_id = mongo_service.sync_fs.put(await file.read(), filename=file.filename, id=id)

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
    file: UploadFile,
    request: Request,
    mongo_service: Annotated[MongoService, Depends(get_mongo_service)],
    rag_service: Annotated[RagService, Depends(get_rag_service)],
    upload_service: Annotated[UploadService, Depends(get_upload_service)],
    conversation_id: Optional[str] = Query(None),
):

    if file and file.size:
        logger.info("file uploading... " + str(file.size / 1000000) + "MB")
    message_text = "A file has been uploaded, use the search text and document tool to access it using the next user prompt."

    # Read the uploaded file
    uploaded_file_content = await file.read()
    # uploaded_file_stream = io.BytesIO(uploaded_file_content)

    if not conversation_id or conversation_id in ["null", "undefined"]:
        # Create a new conversation
        new_conversation = Conversation(id=ObjectId(), user_id=ObjectId(request.state.user_id))
        conversation = await mongo_service.engine.save(new_conversation)

        # Save the uploaded file to GridFS
        one_file_id = mongo_service.sync_fs.put(uploaded_file_content, filename=file.filename, metadata={"conversation_id": str(new_conversation.id)})  # noqa: E501
        # conversation.uploaded_files_ids = [one_file_id]
        # await mongo_service.engine.save(conversation)

        # Create a new message for the new conversation
        new_message = Message(
            id=ObjectId(),
            conversation_id=conversation.id,
            content=message_text,
            is_from_human=True,
            user_id=ObjectId(request.state.user_id),
        )

        await mongo_service.engine.save(new_message)
        await rag_service.insert_to_rag(str(conversation.id))
        return {
            "message": "Contract uploaded",
            "file_id": str(one_file_id), # TODO: change that to get concatenated file maybe
            "conversation_id": str(conversation.id),
        }
    else:
        # Existing conversation
        conversation = await mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))
        if conversation:
            one_file_id = mongo_service.sync_fs.put(uploaded_file_content, filename=file.filename, metadata={"conversation_id": str(conversation_id)})  # noqa: E501
            # conversation.uploaded_files_ids.append(one_file_id)
            # await mongo_service.engine.save(conversation)
            # Create a new message for the existing conversation
            new_message = Message(
                id=ObjectId(),
                conversation_id=conversation.id,
                content=message_text,
                is_from_human=True,
                user_id=ObjectId(request.state.user_id),
            )

            await mongo_service.engine.save(new_message)
            await rag_service.insert_to_rag(str(conversation_id))
            return {
                "message": "Contract uploaded",
                "file_id": str(one_file_id),
                "conversation_id": str(conversation.id),
            }
        else:
            return {"error": "Conversation not found"}



@router.get("")
async def get_all_conversation_files(
    mongo_service: Annotated[MongoService, Depends(get_mongo_service)], conversation_id: Optional[str] = Query(None)
):
    if not conversation_id:
        return JSONResponse("Please provide a conversation_id", 400)

    # Fetch the conversation by ID
    conversation = await mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))
    print(conversation)
    # Find all files associated with the conversation ID
    all_conversation_files = list(mongo_service.sync_fs.find({"metadata.conversation_id": conversation_id}))
    print('t ', all_conversation_files)
    response: FileResponse = FileResponse()

    # If there's a design ID, fetch the design file
    if conversation and conversation.design_id:
        design = mongo_service.sync_fs.find_one({"_id": ObjectId(conversation.design_id)})
        if design:
            response.design = File(name=design.filename, size=design.length)

    # Process all files associated with the conversation
    if conversation and all_conversation_files:
        files = []
        for grid_out in all_conversation_files:
            # Access file attributes safely
            files.append(File(name=grid_out.filename, type=grid_out.content_type, size=grid_out.length))
        response.guidelines = files

    logger.info(response)
    return response
