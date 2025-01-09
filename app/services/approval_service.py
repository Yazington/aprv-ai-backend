import asyncio
import concurrent.futures
from io import BytesIO
from typing import Annotated, List, Tuple, Union

import fitz  # type: ignore
from fastapi.params import Depends
from gmft.pdf_bindings import PyPDFium2Document  # type: ignore
from gridfs import GridOut
from odmantic import ObjectId

from app.config.logging_config import logger
from app.models.conversation import Conversation
from app.models.llm_ready_page import BrandGuidelineReviewResource, LLMPageInferenceResource
from app.models.review import Review
from app.models.task import Task, TaskStatus
from app.services.mongo_service import MongoService, get_mongo_service
from app.services.openai_service import OpenAIClient, get_openai_client
from app.services.pdf_extraction_service import PDFExtractionService, get_pdf_extraction_service
from app.services.rag_service import RagService, get_rag_service
from app.utils.tiktoken import num_tokens_from_messages


class ApprovalService:
    def __init__(
        self,
        mongo_service: MongoService,
        rag_service: RagService,
        openai_client: OpenAIClient,
        pdf_extraction_service: PDFExtractionService,
    ):
        self.rag_service = rag_service
        self.mongo_service = mongo_service
        self.openai_client = openai_client
        self.pdf_extraction_service = pdf_extraction_service

    async def validate_design_against_all_documents(self, pdf_bytes, design_bytes, conversation_id):

        extracted_pdf_resources, doc = await self.pdf_extraction_service.extract_tables_and_text_from_file(
            pdf_bytes, keep_document_open=True
        )

        try:
            inference_result_resources: List[LLMPageInferenceResource] = []

            page_data_list = []

            # Sequentially extract necessary data from the doc
            for extracted_pdf_content in extracted_pdf_resources:
                fitz_page = doc.load_page(extracted_pdf_content.page_number)

                # Extract images
                guideline_image_bytes_list = self.get_page_images_as_bytes(fitz_page, doc)
                extracted_pdf_content.give_images = guideline_image_bytes_list

                if not extracted_pdf_content.given_tables:
                    extracted_pdf_content.given_tables = []

                # Store the extracted content for concurrent processing
                page_data_list.append(extracted_pdf_content)

            doc.close()

            # Create tasks for concurrent processing of each page
            tasks = [
                asyncio.create_task(self.process_page_content(extracted_pdf_content, design_bytes, conversation_id))
                for extracted_pdf_content in page_data_list
            ]

            # Run tasks concurrently
            inference_result_resources = await asyncio.gather(*tasks)

        except Exception as e:
            doc.close()
            raise

        return inference_result_resources

    async def process_page_content(self, extracted_pdf_content, design_bytes, conversation_id):
        content, number_of_token = await self.compare_design_against_page(
            extracted_pdf_content.given_text,
            extracted_pdf_content.given_tables,
            design_bytes,
            extracted_pdf_content.give_images,
            self.openai_client,
        )

        if not content:
            raise Exception(f"Failed to get structured content for conversation id: {conversation_id}")

        await self.mongo_service.engine.save(
            Review(
                id=ObjectId(),
                conversation_id=ObjectId(conversation_id),
                page_number=extracted_pdf_content.page_number,
                review_description=content.review_description,
                guideline_achieved=content.guideline_achieved,
            )
        )

        page_inference_resource = LLMPageInferenceResource()
        page_inference_resource.page_number = extracted_pdf_content.page_number
        page_inference_resource.given_text = extracted_pdf_content.given_text
        page_inference_resource.given_tables = extracted_pdf_content.given_tables
        page_inference_resource.inference_response = content

        return page_inference_resource

    async def background_process_design(
        self,
        conversation_id: str,
    ):
        logger.info("Starting background task for conversation_id: %s", conversation_id)

        conversation = await self.mongo_service.engine.find_one(Conversation, Conversation.id == ObjectId(conversation_id))

        task = await self.create_task(conversation_id)

        if not conversation:
            task.status = TaskStatus.FAILED.name
            logger.error("task failed: no conversation for conversation_id ", str(conversation_id))
            await self.mongo_service.engine.save(task)
            return

        try:

            contract_id = conversation.guidelines_id
            design_id = conversation.design_id

            if not contract_id or not design_id:
                task.status = TaskStatus.FAILED.name
                logger.error("task failed: no contract or design for conversation_id ", str(conversation_id))
                await self.mongo_service.engine.save(task)
                return

            conversation.design_process_task_id = task.id
            await self.mongo_service.engine.save(conversation)

            contract_bytes, design_bytes = self.get_existing_files_as_bytes(self.mongo_service, contract_id, design_id)

            llm_inference_per_page_resources = await self.validate_design_against_all_documents(
                contract_bytes,
                design_bytes,
                conversation_id,
            )

            if not llm_inference_per_page_resources or llm_inference_per_page_resources == []:
                raise Exception("Failed to process pdf")

            logger.info("Saving PDF content as a plain text file")

            # Convert the list to a plain text string (each item on a new line)
            text_data = "\n".join(str(resource) for resource in llm_inference_per_page_resources)

            # Save the text data to a byte stream
            text_byte_array = BytesIO(text_data.encode("utf-8"))

            # Store the text byte array in GridFS using `put()`
            txt_file_id = self.mongo_service.fs.put(text_byte_array, filename=f"{conversation_id}_generated.txt")

            # Update the task with success status and store the text file ID
            task.status = TaskStatus.COMPLETE.name
            task.generated_txt_id = txt_file_id
            await self.mongo_service.engine.save(task)
            await self.rag_service.insert_to_rag(conversation_id)
        except Exception as e:
            # Update the task with a failed status if an exception occurs
            task.status = TaskStatus.FAILED.name
            logger.error(f"Task failed: {str(e)}")
            await self.mongo_service.engine.save(task)

    def get_existing_files_as_bytes(self, mongo_service: MongoService, guidelines_id, design_id):
        guidelines_file: GridOut = self.mongo_service.fs.find_one({"_id": guidelines_id})
        design_file: GridOut = self.mongo_service.fs.find_one({"_id": design_id})

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

    async def create_task(self, conversation_id):
        if not conversation_id:
            logger.error("No conversation id provided for processing")
            raise Exception("No conversation id provided for processing")

        try:
            task = Task(id=ObjectId(), conversation_id=ObjectId(conversation_id), status=TaskStatus.IN_PROGRESS.name)
            await self.mongo_service.engine.save(task)
            logger.info("Task saved successfully")
        except Exception as e:
            logger.error("Error saving task to DB: %s", str(e))
            raise
        return task

    def get_page_images_as_bytes(self, page, pdf_document: fitz.Document) -> List[bytes]:
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
        self, text: str, tables: List[str], design_bytes: bytes, guideline_image_bytes_list: List[bytes], openai_client: OpenAIClient
    ) -> Tuple[Union[BrandGuidelineReviewResource, None], int]:
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

        content: Union[BrandGuidelineReviewResource, None] = await openai_client.get_openai_multi_images_response(
            """
    You are a brand licensing assistant reviewing designs against brand licensing guidelines. You want to ensure that the design respects everything
    from the brand guideline content that would be given to you. You are the one reporting if there is any issues to the designer. You have to be detailed and concise
    and you have to make sure that the design respects every single word/line/sentence and idea that is GIVEN TO YOU.
    You are an assistant that evaluates design compliance based on provided documents. If the design is not available, do not attempt to generate a compliance score. Instead, politely inform the user that the design is required to perform the evaluation.
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

    def init_subprocess_models(self):
        global detector
        global formatter
        from gmft.auto import AutoTableDetector, AutoTableFormatter  # type:ignore

        detector = AutoTableDetector()
        formatter = AutoTableFormatter()

    # def process_page(self, page_number, pdf_bytes):
    #     # Re-initialize any global objects to ensure they are available in the subprocess
    #     global detector
    #     global formatter

    #     # Open the documents
    #     pdf_document = fitz.open("pdf", pdf_bytes)
    #     doc = PyPDFium2Document(pdf_bytes)

    #     # Get the page
    #     fitz_page = pdf_document.load_page(page_number)
    #     page = doc.get_page(page_number)

    #     # Extract text from the page
    #     text = fitz_page.get_text("text")

    #     # Extract tables
    #     logger.info(f"Extracting tables from page {page_number}")
    #     tables = detector.extract(page)
    #     logger.info(f"Formatting tables from page {page_number}")
    #     text_tables = self.extract_and_store_tables_as_string(tables, formatter)

    #     # Build the result
    #     page_inference_resource = LLMPageInferenceResource()
    #     page_inference_resource.page_number = page_number
    #     page_inference_resource.given_text = text
    #     page_inference_resource.given_tables = text_tables

    #     # Close documents
    #     pdf_document.close()
    #     doc.close()

    #     return page_inference_resource

    def extract_and_store_tables_as_string(self, tables, formatter):

        extracted_data: List[str] = []  # type:ignore
        for table in tables:
            # Format the table using the formatter
            formatted_table = formatter.format(table)
            df = formatted_table.df()
            if not df.empty:
                extracted_data.append(df.to_string(index=False))
        return extracted_data

    # async def extract_tables_and_text_from_file(self, pdf_bytes):
    #     try:
    #         # Open the document to get the number of pages
    #         doc = PyPDFium2Document(pdf_bytes)
    #         num_pages = len(doc)
    #         doc.close()

    #         loop = asyncio.get_running_loop()
    #         inference_result_resources: List[LLMPageInferenceResource] = []  # type:ignore

    #         with concurrent.futures.ProcessPoolExecutor(max_workers=10, initializer=self.init_subprocess_models) as pool:
    #             tasks = [loop.run_in_executor(pool, self.process_page, page_number, pdf_bytes) for page_number in range(num_pages)]
    #             inference_result_resources = await asyncio.gather(*tasks)
    #     except Exception as e:
    #         logger.error(f"An error occurred: {e}")
    #         raise

    #     return inference_result_resources


def get_approval_service(
    mongo_service: Annotated[MongoService, Depends(get_mongo_service)],
    rag_service: Annotated[RagService, Depends(get_rag_service)],
    openai_client: Annotated[OpenAIClient, Depends(get_openai_client)],
    pdf_extraction_service: Annotated[PDFExtractionService, Depends(get_pdf_extraction_service)],
):
    return ApprovalService(mongo_service, rag_service, openai_client, pdf_extraction_service)
