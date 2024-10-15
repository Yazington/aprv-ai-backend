import io
import logging
from typing import Union

from fastapi.encoders import jsonable_encoder
import fitz  # type: ignore
from fastapi import APIRouter, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from fpdf import FPDF
from gridfs import GridOut
from models.review import Review
from models.conversation import Conversation
from models.task import Task, TaskStatus
from odmantic import ObjectId
from services.mongo_service import MongoService, mongo_service
from services.openai_service import BrandGuideline, OpenAIClient, openai_client

router = APIRouter(
    prefix="/conversations",
    tags=["Conversation"],
)


logging.basicConfig(
    level=logging.INFO,  # or DEBUG for more detailed logs
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],  # Logs will be printed to console
)


@router.get("")
async def get_conversations(user_id: str = Query(...), mongo_service: MongoService = mongo_service):
    if not user_id:
        return None
    return await mongo_service.engine.find(Conversation, Conversation.user_id == ObjectId(user_id))
    # print(conversations)
    # return None


@router.get("/process-design")
async def process_design(
    background_tasks: BackgroundTasks,
    conversation_id: str = Query(...),
    mongo_service: MongoService = mongo_service,
    openai_client: OpenAIClient = openai_client,
):
    if not conversation_id:
        return {"error": "conversation_id is required"}

    # Start the background task
    background_tasks.add_task(background_process_design, conversation_id, mongo_service, openai_client)

    # Return immediate response with status code 200
    return {"message": "Process started", "conversation_id": conversation_id}


# Polling endpoint to check if task is done
@router.get("/process-status")
async def process_status(conversation_id: str = Query(...), mongo_service: MongoService = mongo_service):
    if not conversation_id:
        return JSONResponse("Please provide a conversation_id", status_code=400)

    conversation_of_task = await mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))

    if not conversation_of_task.design_process_task_id:
        return JSONResponse("conversation doesn't have a task", status_code=400)

    task_of_conversation = await mongo_service.engine.find_one(Task, Task.id == conversation_of_task.design_process_task_id)
    if task_of_conversation.status == TaskStatus.IN_PROGRESS.name:
        return JSONResponse(jsonable_encoder({"task_id": str(task_of_conversation.id)}), status_code=202)
    if task_of_conversation.status == TaskStatus.COMPLETE.name:
        return JSONResponse(jsonable_encoder({"task_id": str(task_of_conversation.id)}), status_code=200)


@router.get("/process-result")
async def get_process_result(task_id: str = Query(...), mongo_service: MongoService = mongo_service):
    if not task_id:
        return JSONResponse("Please provide a task_id", status_code=400)

    task_of_conversation = await mongo_service.engine.find_one(Task, Task.id == ObjectId(task_id))
    if not task_of_conversation.generated_pdf_id:
        return JSONResponse(
            jsonable_encoder(
                {"task_id": None, "error": "there was an issue with the given task. It was probably never created or in progress"}
            ),
            status_code=500,
        )
    return await mongo_service.engine.find(Review, Review.conversation_id == task_of_conversation.conversation_id)


# Simulated background task function
async def background_process_design(conversation_id: str, mongo_service: MongoService, openai_client: OpenAIClient):
    logging.info("Starting background task for conversation_id: %s", conversation_id)

    if not conversation_id:
        logging.error("No conversation id provided for processing")
        raise Exception("No conversation id provided for processing")

    try:
        task = Task(id=ObjectId(), conversation_id=ObjectId(conversation_id), status=TaskStatus.IN_PROGRESS.name)
        await mongo_service.engine.save(task)
        logging.info("Task saved successfully")
    except Exception as e:
        logging.error("Error saving task to DB: %s", str(e))
        raise

    try:
        conversation = await mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))
        if not conversation:
            task.status = TaskStatus.FAILED.name
            logging.error("task failed: no conversation for conversation_id ", str(conversation_id))
            await mongo_service.engine.save(task)
            return

        contract_id = conversation.contract_id
        design_id = conversation.design_id

        if not contract_id or not design_id:
            task.status = TaskStatus.FAILED.name
            logging.error("task failed: no contract or design for conversation_id ", str(conversation_id))
            await mongo_service.engine.save(task)
            return

        contract_file: GridOut = mongo_service.fs.find_one({"_id": contract_id})
        design_file: GridOut = mongo_service.fs.find_one({"_id": design_id})

        if not contract_file:
            logging.error("No contract file/null file")
            raise Exception("No contract file/null file")

        if not contract_file:
            logging.error("No design file/null file")
            raise Exception("No design file/null file")

        # Read the contract bytes
        contract_bytes = contract_file.read()

        # Read the design bytes
        design_bytes = design_file.read()

        # Use contract_bytes to open the PDF from memory
        pdf_document = fitz.open("pdf", contract_bytes)

        # Initialize a new PDF using FPDF
        pdf_output = FPDF()
        pdf_output.set_auto_page_break(auto=True, margin=15)

        logging.info("starting processing for pdf doc")
        count = 0
        # Loop through each page in the PDF
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)

            # Extract text from the page
            text = page.get_text("text")

            # Extract images from the page
            images = page.get_images(full=True)

            guideline_image_bytes_list = []
            # Loop through each image on the page
            for img in images:
                xref = img[0]
                base_image = pdf_document.extract_image(xref)
                guideline_image_bytes = base_image["image"]
                guideline_image_bytes_list.append(guideline_image_bytes)

            # Prepare the prompt (this is a placeholder, you can replace it with your actual prompt)
            prompt = f"""
THE FIRST IMAGE IS THE DESIGN AND THE OTHER IMAGES ARE PART OF A BRAND LICENSING BRAND GUIDELINE PAGE!
Design: first image
Brand Licensing Brand Guideline Images: all images that are not the first image

Brand Licensing Brand Guideline Page Text:
{text}
1. Analyze the text + `images that arent the first image` of the Brand Licensing Guideline, focusing specifically on relevant directives or guidelines like 'must' 'shall' 'required to' 'may not' 'shall not', 'prohibited', etc. Ignore any general context, introductions, table of contents, or explanations. Determine if the text is applicable to the design. If the text includes relevant directives or guidelines, set "is_review_required" to True; otherwise, set it to False.
2. Provide a description of wether or not the design is good with regards to the all images and text from the brand licensing brand guideline ("review_description")
3. Provide a score between False and True indicating the suitability of the design for the page content. Evaluate whether the design is suitable for the following page of brand licensing brand guideline. (set False or True only for "guideline_achieved"). 
            """
            print(prompt)

            content: Union[BrandGuideline | None] = await openai_client.get_openai_multi_images_response(
                """
You are a brand licensing professional reviewing designs against brand licensing guidelines
                """,
                prompt,
                design_bytes,
                guideline_image_bytes_list,
            )
            print(content)
            if not content:
                raise Exception(f"Failed to get structured content for conversation id: {conversation_id}")

            if content and content.is_review_required:
                review = await mongo_service.engine.save(
                    Review(
                        id=ObjectId(),
                        conversation_id=conversation.id,
                        review_description=content.review_description,
                        guideline_achieved=content.guideline_achieved,
                    )
                )

            # Add a new page to the output PDF
            pdf_output.add_page()

            # Write the content from OpenAI to the new PDF page
            pdf_output.set_font("Arial", size=12)
            if content and content.is_review_required:
                pdf_output.multi_cell(0, 10, f"Page {page_num + 1}\n\n{review.review_description}\n\n{text}")
            else:
                pdf_output.multi_cell(0, 10, f"Page {page_num + 1}\n\n{text}")
            count += 1
            if count == 2:
                break

        pdf_document.close()

        logging.info("Saving pdf")
        # Save the PDF content to a bytearray
        pdf_data = pdf_output.output(dest="S")  # Returns bytearray

        # Save the bytearray to an in-memory buffer
        pdf_buffer = io.BytesIO(pdf_data)

        # Store the PDF in GridFS using `put()`
        pdf_file_id = mongo_service.fs.put(pdf_buffer.getvalue(), filename=f"{conversation_id}_generated.pdf")

        # Update the task with success status and store the PDF file ID
        task.status = TaskStatus.COMPLETE.name
        task.generated_pdf_id = pdf_file_id
        await mongo_service.engine.save(task)

    except Exception as e:
        task.status = TaskStatus.FAILED.name
        logging.error(f"task failed: {str(e)}")
        await mongo_service.engine.save(task)
