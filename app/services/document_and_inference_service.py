import asyncio
import concurrent.futures
from io import BytesIO
from typing import List, Tuple, Union

import fitz  # type: ignore
from config.logging_config import logger
from gmft.pdf_bindings import PyPDFium2Document  # type: ignore
from gridfs import GridOut
from models.conversation import Conversation
from models.llm_ready_page import BrandGuideline, LLMPageInferenceResource, LLMPageRequest
from models.message import Message
from models.review import Review
from models.task import Task, TaskStatus
from odmantic import ObjectId
from services.mongo_service import MongoService
from services.openai_service import OpenAIClient
from services.rag_service import insert_to_rag
from utils.tiktoken import num_tokens_from_messages

# TODO: refactor service to split into 2 (document processing and second part goes in openai_service)
# higher order controller should have 2 calles to each service
# In the case below, didnt want to loop again and do processing only once (infer_design_against_all)


async def infer_design_against_all(pdf_bytes, design_bytes, openai_client: OpenAIClient, conversation_id, mongo_service: MongoService):
    from gmft.auto import (
        AutoTableDetector,  # type:ignore
        AutoTableFormatter,
    )

    formatter = AutoTableFormatter()
    detector = AutoTableDetector()
    try:
        # opening document 2 times (one for text + images and second for tables)
        # reason is that fitz or PyPDFium2Document doesnt extract text as well as images, only images (need to investigate more)
        doc = PyPDFium2Document(pdf_bytes)
        pdf_document = fitz.open("pdf", pdf_bytes)
        if not doc or not pdf_document:
            raise Exception("Failed to process contact doc is null")

        inference_result_resources: List[LLMPageInferenceResource] = []

        for page_number, page in enumerate(doc, start=0):
            llm_page_request: LLMPageRequest = LLMPageRequest()
            llm_page_request.page_number = page_number
            fitz_page = pdf_document.load_page(page_number)

            # Extract text from the page
            text = fitz_page.get_text("text")
            llm_page_request.given_text = text

            # Extract images
            # page = pdf_document.load_page(page_number)
            guideline_image_bytes_list = get_page_images_as_bytes(fitz_page, pdf_document)
            llm_page_request.give_images = guideline_image_bytes_list

            # Extract tables
            tables = detector.extract(page)
            text_tables = extract_and_store_tables_as_string(tables, formatter)
            llm_page_request.given_tables = text_tables

            content: Union[BrandGuideline, None]
            number_of_token: int

            content, number_of_token = await compare_design_against_page(
                llm_page_request.given_text, llm_page_request.given_tables, design_bytes, llm_page_request.give_images, openai_client
            )

            # print("num tokens used: ", number_of_token)
            if not content:
                raise Exception(f"Failed to get structured content for conversation id: {conversation_id}")

            if content:
                await mongo_service.engine.save(
                    Review(
                        id=ObjectId(),
                        conversation_id=ObjectId(conversation_id),
                        page_number=page_number,
                        review_description=content.review_description,
                        guideline_achieved=content.guideline_achieved,
                    )
                )
                page_inference_resource: LLMPageInferenceResource = LLMPageInferenceResource()
                page_inference_resource.page_number = page_number
                page_inference_resource.given_text = llm_page_request.given_text
                page_inference_resource.given_tables = llm_page_request.given_tables
                page_inference_resource.inference_response = content
                inference_result_resources.append(page_inference_resource)
        doc.close()
        pdf_document.close()
    except Exception as e:
        doc.close()
        pdf_document.close()
        raise Exception(e) from e

    return inference_result_resources


# def extract_and_store_tables_as_string(tables):
#     extracted_data: List[str] = []
#     for idx, table in enumerate(tables):
#         # Format the table using the formatter
#         formatted_table = formatter.format(table)
#         df = formatted_table.df()
#         if not df.empty:
#             extracted_data.append(df.to_string(index=False))

#     return extracted_data


async def background_process_design(conversation_id: str, mongo_service: MongoService, openai_client: OpenAIClient):
    logger.info("Starting background task for conversation_id: %s", conversation_id)

    conversation = await mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))
    if conversation.design_process_task_id:
        return
    task = await create_task(conversation_id, mongo_service)

    if not conversation:
        task.status = TaskStatus.FAILED.name
        logger.error("task failed: no conversation for conversation_id ", str(conversation_id))
        await mongo_service.engine.save(task)
        return

    try:

        contract_id = conversation.guidelines_id
        design_id = conversation.design_id

        if not contract_id or not design_id:
            task.status = TaskStatus.FAILED.name
            logger.error("task failed: no contract or design for conversation_id ", str(conversation_id))
            await mongo_service.engine.save(task)
            return

        conversation.design_process_task_id = task.id
        await mongo_service.engine.save(conversation)

        contract_bytes, design_bytes = get_existing_files_as_bytes(mongo_service, contract_id, design_id)

        llm_inference_per_page_resources = await infer_design_against_all(
            contract_bytes, design_bytes, openai_client, conversation_id, mongo_service
        )

        if not llm_inference_per_page_resources or llm_inference_per_page_resources == []:
            raise Exception("Failed to process pdf")

        logger.info("Saving PDF content as a plain text file")

        # Convert the list to a plain text string (each item on a new line)
        text_data = "\n".join(str(resource) for resource in llm_inference_per_page_resources)

        # Save the text data to a byte stream
        text_byte_array = BytesIO(text_data.encode("utf-8"))

        # Store the text byte array in GridFS using `put()`
        txt_file_id = mongo_service.fs.put(text_byte_array, filename=f"{conversation_id}_generated.txt")

        # Update the task with success status and store the text file ID
        task.status = TaskStatus.COMPLETE.name
        task.generated_txt_id = txt_file_id
        await mongo_service.engine.save(task)
        await insert_to_rag(conversation_id, mongo_service)
    except Exception as e:
        # Update the task with a failed status if an exception occurs
        task.status = TaskStatus.FAILED.name
        logger.error(f"Task failed: {str(e)}")
        await mongo_service.engine.save(task)


def get_existing_files_as_bytes(mongo_service: MongoService, guidelines_id, design_id):
    guidelines_file: GridOut = mongo_service.fs.find_one({"_id": guidelines_id})
    design_file: GridOut = mongo_service.fs.find_one({"_id": design_id})

    if not guidelines_file:
        logger.error("No contract file/null file")
        raise Exception("No contract file/null file")

    if not design_file:
        logger.error("No design file/null file")
        raise Exception("No design file/null file")

        # Read the contract bytes
    contract_bytes = guidelines_file.read()

    # Read the design bytes
    design_bytes = design_file.read()
    return contract_bytes, design_bytes


async def create_task(conversation_id, mongo_service):
    if not conversation_id:
        logger.error("No conversation id provided for processing")
        raise Exception("No conversation id provided for processing")

    try:
        task = Task(id=ObjectId(), conversation_id=ObjectId(conversation_id), status=TaskStatus.IN_PROGRESS.name)
        await mongo_service.engine.save(task)
        logger.info("Task saved successfully")
    except Exception as e:
        logger.error("Error saving task to DB: %s", str(e))
        raise
    return task


def get_page_images_as_bytes(page, pdf_document: open) -> List[bytes]:
    # Extract images from the page
    images = page.get_images(full=True)
    if len(images) > 20:
        return []
    guideline_image_bytes_list = []
    # Loop through each image on the page
    for img in images:
        xref = img[0]
        base_image = pdf_document.extract_image(xref)
        guideline_image_bytes = base_image["image"]
        guideline_image_bytes_list.append(guideline_image_bytes)

    return guideline_image_bytes_list


async def compare_design_against_page(
    text: str, tables: List[str], design_bytes: bytes, guideline_image_bytes_list: bytes, openai_client: OpenAIClient
) -> Tuple[Union[BrandGuideline, None], int]:
    # Prepare the prompt
    guideline_text = "None" if text == "" else text
    guideline_tables = "None" if not tables else "\n".join(tables)

    prompt = (
        f"The first image is the design. All other images are part of a brand licensing guideline.\n"
        f"Design Image: the first image.\n"
        f"Brand Guideline Images: all images after the first one.\n\n"
        f"Brand Guideline Text:\n{guideline_text}\n\n"
        f"Brand Guideline Tables:\n{guideline_tables}\n\n"
        "Please follow these steps:\n"
        "1. Check if the Brand Guideline Text is related to brand guidelines. If it’s not, set 'guideline_achieved' to None and stop. If it is, continue.\n"
        "2. review_description (string): For each part of the Brand Guideline (text, images, tables), describe if the design aligns with it.\n"
        "3. guideline_achieved (True, False, or None): Rate how suitable the design is based on the Brand Guideline. If the Brand Guideline isn’t relevant, return None."
    )

    content: Union[BrandGuideline | None] = await openai_client.get_openai_multi_images_response(
        """
You are a brand licensing professional reviewing designs against brand licensing guidelines. You want to ensure that the design respects everything
from the brand guideline content that would be given to you. You are the one reporting if there is any issues to the designer. You have to be detailed and concise
and you have to make sure that the design respects every single word/line/sentence and idea that is GIVEN TO YOU.
        """,
        prompt,
        design_bytes,
        guideline_image_bytes_list,
    )
    # print(prompt)
    # print(content)
    if content:
        tokens_used = num_tokens_from_messages([prompt, content.review_description])

    return content, tokens_used


# Ensure these are properly imported or defined in your code
# from your_module import LLMPageInferenceResource, LLMPageRequest, detector, formatter, logger


def init_subprocess_models():
    global detector
    global formatter
    from gmft.auto import AutoTableDetector, AutoTableFormatter

    detector = AutoTableDetector()
    formatter = AutoTableFormatter()


def process_page(page_number, pdf_bytes):
    # Re-initialize any global objects to ensure they are available in the subprocess
    global detector
    global formatter

    # Open the documents
    pdf_document = fitz.open("pdf", pdf_bytes)
    doc = PyPDFium2Document(pdf_bytes)

    # Get the page
    fitz_page = pdf_document.load_page(page_number)
    page = doc.get_page(page_number)

    # Extract text from the page
    text = fitz_page.get_text("text")

    # Extract tables
    logger.info(f"Extracting tables from page {page_number}")
    tables = detector.extract(page)
    logger.info(f"Formatting tables from page {page_number}")
    text_tables = extract_and_store_tables_as_string(tables, formatter)

    # Build the result
    page_inference_resource = LLMPageInferenceResource()
    page_inference_resource.page_number = page_number
    page_inference_resource.given_text = text
    page_inference_resource.given_tables = text_tables

    # Close documents
    pdf_document.close()
    doc.close()

    return page_inference_resource


def extract_and_store_tables_as_string(tables, formatter):

    extracted_data: List[str] = []
    for table in tables:
        # Format the table using the formatter
        formatted_table = formatter.format(table)
        df = formatted_table.df()
        if not df.empty:
            extracted_data.append(df.to_string(index=False))
    return extracted_data


async def extract_tables_and_text_from_file(pdf_bytes):
    try:
        # Open the document to get the number of pages
        doc = PyPDFium2Document(pdf_bytes)
        num_pages = len(doc)
        doc.close()

        loop = asyncio.get_running_loop()
        inference_result_resources: List[LLMPageInferenceResource] = []

        with concurrent.futures.ProcessPoolExecutor(max_workers=6, initializer=init_subprocess_models) as pool:
            tasks = [loop.run_in_executor(pool, process_page, page_number, pdf_bytes) for page_number in range(num_pages)]
            inference_result_resources = await asyncio.gather(*tasks)
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise

    return inference_result_resources


async def guideline_to_txt_and_save_message_with_new_file(
    mongo_service: MongoService, file_id: ObjectId, conversation_id: str, message: Message
):
    contract_file: GridOut = mongo_service.fs.find_one({"_id": file_id})
    if not contract_file:
        logger.error("No contract file/null file")
        raise Exception("No contract file/null file")

    logger.info("guideline to txt start: reading bytes ...")
    # Read the contract bytes
    contract_bytes = contract_file.read()
    logger.info("bytes read ...")

    llm_inference_per_page_resources = await extract_tables_and_text_from_file(contract_bytes)
    logger.info("tables extracted ...")

    if not llm_inference_per_page_resources or llm_inference_per_page_resources == []:
        raise Exception("Failed to process pdf")

    logger.info("Saving PDF content as a plain text file")

    # Convert the list to a plain text string (each item on a new line)
    text_data = "\n".join(str(resource) for resource in llm_inference_per_page_resources)
    # print("len text data: ", len(text_data))
    # Save the text data to a byte stream
    text_byte_array = BytesIO(text_data.encode("utf-8"))

    # Store the text byte array in GridFS using `put()`
    txt_file_id = mongo_service.fs.put(text_byte_array, filename=f"{conversation_id}_file_upload.txt")
    message.uploaded_pdf_id = txt_file_id
    await mongo_service.engine.save(message)
    # await insert_to_rag(conversation_id, message, mongo_service)
