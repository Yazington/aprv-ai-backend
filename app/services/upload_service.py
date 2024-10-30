from io import BytesIO
from typing import Annotated

from fastapi import Depends
from gridfs import GridOut
from odmantic import ObjectId

from app.config.logging_config import logger
from app.services.mongo_service import MongoService, get_mongo_service
from app.services.pdf_extraction_service import PDFExtractionService, get_pdf_extraction_service


class UploadService:
    def __init__(self, mongo_service: MongoService, pdf_extraction_service: PDFExtractionService):
        self.mongo_service = mongo_service
        self.pdf_extraction_service = pdf_extraction_service

    async def upload_guideline_and_concat(self, concatenated_file_id: ObjectId, conversation_id: str) -> ObjectId:
        concatenated_guidelines_file: GridOut = self.mongo_service.fs.find_one({"_id": concatenated_file_id})
        if not concatenated_guidelines_file:
            logger.error("No contract file/null file")
            raise Exception("No contract file/null file")

        guideline_bytes = concatenated_guidelines_file.read()

        llm_inference_per_page_resources, _ = await self.pdf_extraction_service.extract_tables_and_text_from_file(guideline_bytes)

        if not llm_inference_per_page_resources or llm_inference_per_page_resources == []:
            raise Exception("Failed to process pdf")

        logger.info("Saving PDF content as a plain text file")

        # Convert the list to a plain text string (each item on a new line)
        text_data = "\n".join(str(resource) for resource in llm_inference_per_page_resources)

        # Save the text data to a byte stream
        text_byte_array = BytesIO(text_data.encode("utf-8"))

        # Store the text byte array in GridFS using `put()`
        return self.mongo_service.fs.put(text_byte_array, filename=f"{conversation_id}_guideline.txt")


def get_upload_service(
    mongo_service: Annotated[MongoService, Depends(get_mongo_service)],
    pdf_extraction_service: Annotated[PDFExtractionService, Depends(get_pdf_extraction_service)],
):
    return UploadService(mongo_service, pdf_extraction_service)
