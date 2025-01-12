import io
from typing import Annotated, Optional, Dict, Any

from fastapi import APIRouter, Depends, Query, Request, UploadFile, HTTPException
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
    id = ObjectId()
    file_id = mongo_service.fs.put(await file.read(), filename=file.filename, id=id)

    if not conversation_id or conversation_id == "null" or conversation_id == "undefined":
        new_conversation = Conversation(id=ObjectId(), design_id=ObjectId(file_id), user_id=ObjectId(request.state.user_id))
        conversation = await mongo_service.engine.save(new_conversation)
        return {
            "message": "Image uploaded and new conversation created",
            "file_id": str(file_id),
            "conversation_id": str(conversation.id),
        }
    else:
        conversation = await mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))
        if conversation:
            conversation.design_id = ObjectId(file_id)
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
    try:
        # Validate file
        if not file or not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")

        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="File must be a PDF")

        file_size_mb = file.size / (1024 * 1024) if file.size else 0
        logger.info(f"Processing PDF upload: {file.filename} ({file_size_mb:.2f}MB)")

        # Read file content
        try:
            uploaded_file_content = await file.read()
            logger.info(f"Successfully read {len(uploaded_file_content)} bytes from upload")
        except Exception as e:
            logger.error(f"Error reading uploaded file: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")

        message_text = "A file has been uploaded, use the search text and document tool to access it using the next user prompt."

        # Handle new conversation case
        if not conversation_id or conversation_id in ["null", "undefined"]:
            try:
                # Create new conversation
                new_conversation = Conversation(id=ObjectId(), user_id=ObjectId(request.state.user_id))
                conversation = await mongo_service.engine.save(new_conversation)
                conversation_id = str(conversation.id)
                logger.info(f"Created new conversation: {conversation_id}")

                # Save file to GridFS
                file_id = mongo_service.fs.put(uploaded_file_content, filename=file.filename)
                conversation.guidelines_ids = [file_id]
                await mongo_service.engine.save(conversation)
                logger.info(f"Saved file to GridFS: {file_id}")

                # Process the file
                processed_ids = await upload_service.process_multiple_guidelines([file_id], conversation_id)
                logger.info(f"Processed file(s), got IDs: {processed_ids}")

                # Create message
                new_message = Message(
                    id=ObjectId(),
                    conversation_id=conversation.id,
                    content=message_text,
                    is_from_human=True,
                    user_id=ObjectId(request.state.user_id),
                    uploaded_pdf_ids=processed_ids,
                )
                await mongo_service.engine.save(new_message)
                await rag_service.insert_to_rag_with_message(conversation_id, new_message)

                return {
                    "message": "Contract uploaded and processed successfully",
                    "file_id": str(file_id),
                    "conversation_id": conversation_id,
                    "processed_ids": [str(pid) for pid in processed_ids],
                }

            except Exception as e:
                logger.error(f"Error processing new conversation upload: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Error processing upload: {str(e)}")

        # Handle existing conversation case
        else:
            try:
                conversation = await mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))
                if not conversation:
                    raise HTTPException(status_code=404, detail="Conversation not found")

                # Save the new PDF to GridFS
                new_file_id = mongo_service.fs.put(uploaded_file_content, filename=file.filename)
                logger.info(f"Saved new file to GridFS: {new_file_id}")

                # Add the new file ID to the list of guidelines
                if not hasattr(conversation, "guidelines_ids"):
                    conversation.guidelines_ids = []
                conversation.guidelines_ids.append(new_file_id)
                await mongo_service.engine.save(conversation)

                # Process the new PDF
                try:
                    processed_ids = await upload_service.process_multiple_guidelines([new_file_id], conversation_id)
                    logger.info(f"Processed new file, got IDs: {processed_ids}")
                except Exception as e:
                    logger.error(f"Error processing file {new_file_id}: {str(e)}")
                    # Remove the file ID from guidelines if processing failed
                    conversation.guidelines_ids.remove(new_file_id)
                    await mongo_service.engine.save(conversation)
                    raise

                # Create message
                new_message = Message(
                    id=ObjectId(),
                    conversation_id=conversation.id,
                    content=message_text,
                    is_from_human=True,
                    user_id=ObjectId(request.state.user_id),
                    uploaded_pdf_ids=processed_ids,
                )
                await mongo_service.engine.save(new_message)
                await rag_service.insert_to_rag_with_message(conversation_id, new_message)

                return {
                    "message": "Contract uploaded and processed successfully",
                    "file_id": str(new_file_id),
                    "conversation_id": conversation_id,
                    "processed_ids": [str(pid) for pid in processed_ids],
                }

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error processing existing conversation upload: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Error processing upload: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in upload_pdf: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get("")
async def get_all_conversation_files(
    mongo_service: Annotated[MongoService, Depends(get_mongo_service)], conversation_id: Optional[str] = Query(None)
):
    if not conversation_id:
        return JSONResponse("Please provide a conversation_id", 400)

    try:
        conversation = await mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))
        if not conversation:
            return JSONResponse("Conversation not found", 404)

        response: FileResponse = FileResponse()

        # Get design file if exists
        if conversation.design_id:
            design = mongo_service.fs.find_one(conversation.design_id)
            if design:
                response.design = File(name=design.filename, size=design.length)
                logger.info(f"Found design file: {design.filename}")

        # Get guideline files
        if hasattr(conversation, "guidelines_ids") and conversation.guidelines_ids:
            guidelines = []
            for guideline_id in conversation.guidelines_ids:
                guideline = mongo_service.fs.find_one({"_id": guideline_id})
                if guideline:
                    guidelines.append(File(name=guideline.filename, size=guideline.length))
                    logger.info(f"Found guideline file: {guideline.filename}")
                else:
                    logger.warning(f"Guideline file not found: {guideline_id}")
            response.guidelines = guidelines

        logger.info(f"Returning {len(response.guidelines or [])} guidelines and {'design' if response.design else 'no design'}")
        return response

    except Exception as e:
        logger.error(f"Error getting conversation files: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving files: {str(e)}")
