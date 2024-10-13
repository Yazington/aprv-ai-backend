import io
import logging

import fitz  # type: ignore
from fastapi import APIRouter, BackgroundTasks, Query
from fpdf import FPDF
from gridfs import GridOut
from models.conversation import Conversation
from models.task import Task, TaskStatus
from odmantic import ObjectId
from services.mongo_service import MongoService, mongo_service
from services.openai_service import OpenAIClient, openai_client

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

        # Loop through each page in the PDF
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)

            # Extract text from the page
            text = page.get_text("text")

            # Extract images from the page
            images = page.get_images(full=True)

            # Loop through each image on the page
            for img in images:
                xref = img[0]
                base_image = pdf_document.extract_image(xref)
                image_bytes = base_image["image"]
                # image_ext = base_image["ext"]

                # Prepare the prompt (this is a placeholder, you can replace it with your actual prompt)
                prompt = f"""
                            THE FIRST IMAGE IS THE DESIGN AND THE OTHER IMAGES ARE PART OF A BRAND LICENSING CONTRACT!

                            Evaluate whether the design is suitable for the following page of brand licensing contract:
                            Design:
                            first image

                            Brand Licensing Contract Text:
                            {text}
                            Brand Licensing Contract Images:
                            all images that are not the first image

                            1. Provide a description of wether or not the design is good with regards to the all images and text from the brand licensing contract 
                            2. Provide a score between 0 and 1 indicating the suitability of the design for the page content (return 0 or 1 only). Write the word "SCORE:" followed by 0 or 1 
                            where 1 means the design is good and 0 means it is not.
                            """
                content_list = []
                print(prompt)
                print(len(design_bytes), len(image_bytes))
                async for content in openai_client.stream_openai_multi_images_response(prompt, design_bytes, image_bytes):
                    print(content, end="")
                    content_list.append(content)

                # Combine the content received from the OpenAI client
                generated_content = "".join(content_list)

                # Add a new page to the output PDF
                pdf_output.add_page()

                # Write the content from OpenAI to the new PDF page
                pdf_output.set_font("Arial", size=12)
                pdf_output.multi_cell(0, 10, f"Page {page_num + 1}\n\n{generated_content}")

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
    # # Check if the task exists in our status tracker
    # if conversation_id not in task_status:
    #     return {"error": "No task found for the given conversation_id"}
    # conversation = await mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))

    # if not conversation.contract_id or not conversation.design_id:
    #     return Response(status_code=415, content="Please upload both contract and design")

    # status = task_status[conversation_id]

    # if status == "done":
    #     # Fetch the result if task is done (e.g., retrieve data from MongoDB or another source)
    #     result = await mongo_service.get_design_result(conversation_id)
    #     return {"status": "done", "conversation_id": conversation_id, "result": result}

    # return {"status": status, "conversation_id": conversation_id}
    pass
