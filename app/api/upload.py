import io
from typing import Annotated, Optional

# from memory_profiler import profile  # type: ignore
import fitz  # type:ignore
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


# @profile
# Handles image uploads and associates them with conversations
# - Creates new conversation if no conversation_id provided
# - Updates existing conversation if conversation_id provided
# - Stores image in MongoDB GridFS
# - Returns file_id and conversation_id
@router.post("/image")
async def upload_image(
    file: UploadFile,
    request: Request,
    mongo_service: Annotated[MongoService, Depends(get_mongo_service)],
    conversation_id: Optional[str] = Query(None),
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


# @profile
# Handles PDF uploads and text extraction
# - Creates new conversation if no conversation_id provided
# - Updates existing conversation if conversation_id provided
# - Merges PDFs if concatenating with existing guidelines
# - Extracts tables and text using PDF extraction service
# - Stores PDF in MongoDB GridFS
# - Creates message with upload notification
# - Returns file_id and conversation_id
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
    uploaded_file_stream = io.BytesIO(uploaded_file_content)

    if not conversation_id or conversation_id in ["null", "undefined"]:
        # Create a new conversation
        new_conversation = Conversation(id=ObjectId(), user_id=ObjectId(request.state.user_id))
        conversation = await mongo_service.engine.save(new_conversation)

        # Save the uploaded file to GridFS
        one_file_id = mongo_service.fs.put(uploaded_file_content, filename=file.filename)
        conversation.guidelines_id = one_file_id
        await mongo_service.engine.save(conversation)

        # Create a new message for the new conversation
        new_message = Message(
            id=ObjectId(),
            conversation_id=conversation.id,
            content=message_text,
            is_from_human=True,
            user_id=ObjectId(request.state.user_id),
        )
        logger.info("using transformer to get tables ...")
        txt_file_id = await upload_service.upload_guideline_and_concat(one_file_id, str(conversation.id))
        new_message.uploaded_pdf_id = txt_file_id
        await mongo_service.engine.save(new_message)
        await rag_service.insert_to_rag_with_message(str(conversation.id), new_message)
        return {
            "message": "Contract uploaded",
            "file_id": str(one_file_id),
            "conversation_id": str(conversation.id),
        }
    else:
        # Existing conversation
        conversation = await mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))
        if conversation:
            # Fetch existing concatenated PDF from GridFS
            existing_guidelines_file_id = conversation.guidelines_id
            merged_pdf = fitz.open()

            if existing_guidelines_file_id:
                existing_pdf_content = mongo_service.fs.get(existing_guidelines_file_id).read()
                existing_pdf_stream = io.BytesIO(existing_pdf_content)
                existing_pdf = fitz.open(stream=existing_pdf_stream, filetype="pdf")
                merged_pdf.insert_pdf(existing_pdf)

            # Open the new uploaded PDF
            uploaded_pdf = fitz.open(stream=uploaded_file_stream, filetype="pdf")
            merged_pdf.insert_pdf(uploaded_pdf)

            # Write concatenated PDF to a BytesIO stream
            concatenated_pdf_stream = io.BytesIO()
            merged_pdf.save(concatenated_pdf_stream)
            concatenated_pdf_stream.seek(0)
            concatenated_pdf_content = concatenated_pdf_stream.read()

            # Save concatenated PDF to GridFS
            concatenated_file_id = mongo_service.fs.put(concatenated_pdf_content, filename=f"concatenated_{conversation.id}.pdf")

            # Update conversation's guidelines_id
            conversation.guidelines_id = concatenated_file_id
            await mongo_service.engine.save(conversation)

            # Optionally, delete old concatenated PDF from GridFS
            if existing_guidelines_file_id:
                mongo_service.fs.delete(existing_guidelines_file_id)

            # Create a new message for the existing conversation
            new_message = Message(
                id=ObjectId(),
                conversation_id=conversation.id,
                content=message_text,
                is_from_human=True,
                user_id=ObjectId(request.state.user_id),
            )
            await mongo_service.engine.save(new_message)
            txt_file_id = await upload_service.upload_guideline_and_concat(concatenated_file_id, str(conversation.id))
            new_message.uploaded_pdf_id = txt_file_id
            await mongo_service.engine.save(new_message)
            await rag_service.insert_to_rag_with_message(str(conversation.id), new_message)
            return {
                "message": "Contract uploaded",
                "file_id": str(concatenated_file_id),
                "conversation_id": str(conversation.id),
            }
        else:
            return {"error": "Conversation not found"}


# @profile
# Retrieves all files associated with a conversation
# - Requires conversation_id parameter
# - Returns design file and guidelines file metadata
# - Returns FileResponse object with file names and sizes
@router.get("")
async def get_all_conversation_files(
    mongo_service: Annotated[MongoService, Depends(get_mongo_service)], conversation_id: Optional[str] = Query(None)
):

    if not conversation_id:
        return JSONResponse("Please provide a conversation_id", 400)
    conversation = await mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))
    response: FileResponse = FileResponse()

    if conversation and conversation.design_id:
        design = mongo_service.fs.find_one(conversation.design_id)
        if design:
            response.design = File(name=design.filename, size=design.length)
    if conversation and conversation.guidelines_id:
        guideline_concatenated = mongo_service.fs.find_one({"_id": conversation.guidelines_id})
        response.guidelines = [File(name=guideline_concatenated.filename, size=guideline_concatenated.length)]
    logger.info(response)
    return response
