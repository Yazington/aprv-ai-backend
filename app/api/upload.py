import io
from typing import List, Optional

from config.logging_config import logger
from fastapi import APIRouter, Query, Request, UploadFile
from fastapi.responses import JSONResponse

# from memory_profiler import profile  # type: ignore
from models.conversation import Conversation
from models.message import Message
from odmantic import ObjectId
from pydantic import BaseModel
from PyPDF2 import PdfReader, PdfWriter
from services.document_and_inference_service import guideline_to_txt_and_save_message_with_new_file
from services.mongo_service import MongoService, mongo_service
from services.rag_service import insert_to_rag_with_message

router = APIRouter(
    prefix="/upload",
    tags=["Upload"],
)


class File(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    size: Optional[int] = None


class FileResponse(BaseModel):
    design: Optional[File] = None
    guidelines: List[File] = []


# @profile
@router.post("/image")
async def upload_image(
    file: UploadFile, request: Request, conversation_id: Optional[str] = Query(None), mongo_service: MongoService = mongo_service
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
@router.post("/pdf")
async def upload_pdf(
    file: UploadFile, request: Request, conversation_id: Optional[str] = Query(None), mongo_service: MongoService = mongo_service
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
        await guideline_to_txt_and_save_message_with_new_file(mongo_service, one_file_id, str(conversation.id), new_message)
        await insert_to_rag_with_message(str(conversation.id), new_message, mongo_service)
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
            existing_pdf_stream = io.BytesIO()
            existing_pdf_reader = None
            if existing_guidelines_file_id:
                existing_pdf_content = mongo_service.fs.get(existing_guidelines_file_id).read()
                existing_pdf_stream = io.BytesIO(existing_pdf_content)
                existing_pdf_reader = PdfReader(existing_pdf_stream)

            # Create PDF readers for the new file
            uploaded_pdf_reader = PdfReader(uploaded_file_stream)

            # Create a blank page matching the size of the uploaded PDF
            page_width = uploaded_pdf_reader.pages[0].mediabox.width
            page_height = uploaded_pdf_reader.pages[0].mediabox.height
            blank_page_writer = PdfWriter()
            blank_page_writer.add_blank_page(width=page_width, height=page_height)
            blank_page_stream = io.BytesIO()
            blank_page_writer.write(blank_page_stream)
            blank_page_stream.seek(0)
            blank_page_reader = PdfReader(blank_page_stream)

            # Concatenate PDFs
            pdf_writer = PdfWriter()
            if existing_pdf_reader:
                for page in existing_pdf_reader.pages:
                    pdf_writer.add_page(page)
                # Add a blank page separator
                pdf_writer.add_page(blank_page_reader.pages[0])
            # Add pages from the new uploaded PDF
            for page in uploaded_pdf_reader.pages:
                pdf_writer.add_page(page)

            # Write concatenated PDF to a BytesIO stream
            concatenated_pdf_stream = io.BytesIO()
            pdf_writer.write(concatenated_pdf_stream)
            concatenated_pdf_stream.seek(0)
            concatenated_pdf_content = concatenated_pdf_stream.read()

            # Save concatenated PDF to GridFS
            new_file_id = mongo_service.fs.put(concatenated_pdf_content, filename=f"concatenated_{conversation.id}.pdf")

            # Update conversation's guidelines_id
            conversation.guidelines_id = new_file_id
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
            await guideline_to_txt_and_save_message_with_new_file(mongo_service, new_file_id, str(conversation.id), new_message)
            await insert_to_rag_with_message(str(conversation.id), new_message, mongo_service)
            return {
                "message": "Contract uploaded",
                "file_id": str(new_file_id),
                "conversation_id": str(conversation.id),
            }
        else:
            return {"error": "Conversation not found"}


# @profile
@router.get("")
async def get_all_conversation_files(conversation_id: Optional[str] = Query(None), mongo_service: MongoService = mongo_service):
    if not conversation_id:
        return JSONResponse("Please provide a conversation_id", 400)
    conversation = await mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))
    print(conversation)
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
