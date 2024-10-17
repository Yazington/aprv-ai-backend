import io
import logging
from typing import List, Tuple, Union

import fitz  # type: ignore
from fpdf import FPDF
from gridfs import GridOut
from utils.tiktoken import num_tokens_from_messages
from models.llm_ready_page import LLMPageInferenceResource, LLMPageRequest, BrandGuideline
from models.conversation import Conversation
from models.review import Review
from models.task import Task, TaskStatus
from odmantic import ObjectId
from services.mongo_service import MongoService
from services.openai_service import MODEL, OpenAIClient
from gmft.auto import AutoTableDetector, AutoTableFormatter
from gmft.pdf_bindings import PyPDFium2Document
from io import BytesIO

detector = AutoTableDetector()
formatter = AutoTableFormatter()


async def infer_design_against_all(pdf_bytes, design_bytes, openai_client: OpenAIClient, conversation_id, mongo_service: MongoService):
    try:
        # opening document 2 times (one for text + images and second for tables)
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
            text_tables = extract_and_store_tables_as_string(tables)
            llm_page_request.given_tables = text_tables
            content: Union[BrandGuideline, None]
            number_of_token: int
            content, number_of_token = await compare_design_against_page_images(
                llm_page_request.given_text, llm_page_request.given_tables, design_bytes, llm_page_request.give_images, openai_client
            )
            print("num tokens used: ", number_of_token)
            if not content:
                raise Exception(f"Failed to get structured content for conversation id: {conversation_id}")

            if content:
                review = await mongo_service.engine.save(
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
        raise Exception(e)

    return inference_result_resources


def extract_and_store_tables_as_string(tables):
    extracted_data: List[str] = []
    for idx, table in enumerate(tables):
        # Format the table using the formatter
        formatted_table = formatter.format(table)
        df = formatted_table.df()
        if not df.empty:
            extracted_data.append(df.to_string(index=False))

    return extracted_data


async def background_process_design(conversation_id: str, mongo_service: MongoService, openai_client: OpenAIClient):
    logging.info("Starting background task for conversation_id: %s", conversation_id)

    task = await create_task(conversation_id, mongo_service)

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

        conversation.design_process_task_id = task.id
        await mongo_service.engine.save(conversation)

        contract_bytes, design_bytes = get_existing_files_as_bytes(mongo_service, contract_id, design_id)

        llm_inference_per_page_resources = await infer_design_against_all(
            contract_bytes, design_bytes, openai_client, conversation_id, mongo_service
        )

        if not llm_inference_per_page_resources or llm_inference_per_page_resources == []:
            raise Exception("Failed to process pdf")

        logging.info("Saving PDF content as a plain text file")

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

    except Exception as e:
        # Update the task with a failed status if an exception occurs
        task.status = TaskStatus.FAILED.name
        logging.error(f"Task failed: {str(e)}")
        await mongo_service.engine.save(task)


def get_existing_files_as_bytes(mongo_service: MongoService, contract_id, design_id):
    contract_file: GridOut = mongo_service.fs.find_one({"_id": contract_id})
    design_file: GridOut = mongo_service.fs.find_one({"_id": design_id})

    if not contract_file:
        logging.error("No contract file/null file")
        raise Exception("No contract file/null file")

    if not design_file:
        logging.error("No design file/null file")
        raise Exception("No design file/null file")

        # Read the contract bytes
    contract_bytes = contract_file.read()

    # Read the design bytes
    design_bytes = design_file.read()
    return contract_bytes, design_bytes


async def create_task(conversation_id, mongo_service):
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
    return task


def get_page_images_as_bytes(page, pdf_document: open) -> List[bytes]:
    # Extract images from the page
    images = page.get_images(full=True)

    guideline_image_bytes_list = []
    # Loop through each image on the page
    for img in images:
        xref = img[0]
        base_image = pdf_document.extract_image(xref)
        guideline_image_bytes = base_image["image"]
        guideline_image_bytes_list.append(guideline_image_bytes)

    return guideline_image_bytes_list


async def compare_design_against_page_images(
    text: str, tables: List[str], design_bytes: bytes, guideline_image_bytes_list: bytes, openai_client: OpenAIClient
) -> Tuple[Union[BrandGuideline, None], int]:
    # Prepare the prompt (this is a placeholder, you can replace it with your actual prompt)
    prompt = f"""
THE FIRST IMAGE IS THE DESIGN AND THE OTHER IMAGES ARE PART OF A BRAND LICENSING BRAND GUIDELINE PAGE!
Design GIVEN TO YOU: first image.
Brand Licensing Brand Guideline Images GIVEN TO YOU: all images that are not the first image.

Brand Licensing Brand Guideline Page Text GIVEN TO YOU:
{'None' if text=='' else text}
Brand Licensing Brand Guideline Page Tables GIVEN TO YOU:
{'None' if tables == [] or tables==None else '\n'.join(tables)}

FIRST, PLEASE READ AND ANALYZE WHAT IS GIVEN TO YOU. THEN AND ONLY THEN YOU MAY COMPARE WHAT YOU HAVE READ AGAINST THE DESIGN/FIRST IMAGE!
1. review_description (string): for each part of what is GIVEN TO YOU, provide a description of wether or not the design respects them.
3. guideline_achieved(True or False or None): provide a score between False and True indicating the suitability of the design for the page content. Comparing to what was GIVEN TO YOU, evaluate whether the design is suitable. If what is GIVEN TO YOU is not applicable return None 
    """

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
