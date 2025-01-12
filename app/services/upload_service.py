from io import BytesIO
from typing import Annotated, List, Tuple, Dict

from fastapi import Depends
from gridfs import GridOut
from odmantic import ObjectId

from app.config.logging_config import logger
from app.services.mongo_service import MongoService, get_mongo_service
from app.services.pdf_extraction_service import PDFExtractionService, get_pdf_extraction_service


# Service for handling file uploads and processing
class UploadService:
    def __init__(self, mongo_service: MongoService, pdf_extraction_service: PDFExtractionService):
        """Initialize upload service with required dependencies"""
        self.mongo_service = mongo_service  # Service for MongoDB operations
        self.pdf_extraction_service = pdf_extraction_service  # Service for PDF processing

    async def process_single_guideline(self, file_id: ObjectId, conversation_id: str) -> ObjectId:
        """
        Process a single PDF file

        Args:
            file_id: ID of the file in GridFS
            conversation_id: ID of the conversation for file naming

        Returns:
            ObjectId: ID of the processed file in GridFS

        Raises:
            Exception: If file is not found or processing fails
        """
        # Retrieve the file from GridFS
        guidelines_file: GridOut = self.mongo_service.fs.find_one({"_id": file_id})
        if not guidelines_file:
            logger.error(f"File not found in GridFS: {file_id}")
            raise Exception("No contract file/null file")

        # Log file details
        logger.info(f"Processing file: {guidelines_file.filename} (ID: {file_id})")
        logger.info(f"File size: {guidelines_file.length / 1024:.2f}KB")

        # Read the file contents into memory
        try:
            guideline_bytes = guidelines_file.read()
            logger.info(f"Successfully read {len(guideline_bytes)} bytes from file")
        except Exception as e:
            logger.error(f"Error reading file {file_id}: {str(e)}")
            raise Exception(f"Failed to read file: {str(e)}")

        try:
            # Extract text and tables from the PDF using the extraction service
            llm_inference_per_page_resources, _ = await self.pdf_extraction_service.extract_tables_and_text_from_file(guideline_bytes)

            # Validate that extraction was successful
            if not llm_inference_per_page_resources or llm_inference_per_page_resources == []:
                logger.error(f"No content extracted from file {file_id}")
                raise Exception("Failed to process pdf - no content extracted")

            logger.info(f"Successfully extracted content from file {file_id}")
            logger.info(f"Number of pages processed: {len(llm_inference_per_page_resources)}")

            # Return the original file ID since we're keeping PDFs in their original format
            return file_id

        except Exception as e:
            logger.error(f"Error processing file {file_id}: {str(e)}")
            raise Exception(f"Failed to process file: {str(e)}")

    async def process_multiple_guidelines(self, file_ids: List[ObjectId], conversation_id: str) -> List[ObjectId]:
        """
        Process multiple PDF files individually

        Args:
            file_ids: List of GridFS file IDs to process
            conversation_id: ID of the conversation for file naming

        Returns:
            List[ObjectId]: List of processed file IDs in GridFS

        Raises:
            Exception: If files are not found or processing fails
        """
        processed_file_ids = []
        failed_files: Dict[str, str] = {}  # file_id -> error message

        logger.info(f"Processing {len(file_ids)} files for conversation {conversation_id}")

        # Process each PDF file individually
        for file_id in file_ids:
            try:
                logger.info(f"Starting processing of file {file_id}")
                processed_id = await self.process_single_guideline(file_id, conversation_id)
                processed_file_ids.append(processed_id)
                logger.info(f"Successfully processed file {file_id} -> {processed_id}")
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Failed to process file {file_id}: {error_msg}")
                failed_files[str(file_id)] = error_msg
                continue

        # Log processing summary
        logger.info(f"Processing complete: {len(processed_file_ids)} succeeded, {len(failed_files)} failed")
        if failed_files:
            logger.error("Failed files:")
            for file_id, error in failed_files.items():
                logger.error(f"  - {file_id}: {error}")

        if not processed_file_ids:
            error_details = "\n".join([f"{fid}: {err}" for fid, err in failed_files.items()])
            raise Exception(f"Failed to process any PDFs. Errors:\n{error_details}")

        return processed_file_ids

    async def upload_guideline_and_concat(self, file_id: ObjectId, conversation_id: str) -> ObjectId:
        """
        Legacy method for backward compatibility
        Now processes a single file and returns its ID
        """
        return await self.process_single_guideline(file_id, conversation_id)


# Dependency injection function for FastAPI
def get_upload_service(
    mongo_service: Annotated[MongoService, Depends(get_mongo_service)],
    pdf_extraction_service: Annotated[PDFExtractionService, Depends(get_pdf_extraction_service)],
):
    """Factory function to create and return an UploadService instance"""
    return UploadService(mongo_service, pdf_extraction_service)
