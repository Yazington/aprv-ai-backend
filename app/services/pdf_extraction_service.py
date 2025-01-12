import os
from typing import Dict, List, Tuple, Any, cast
import boto3
from io import BytesIO
from PyPDF2 import PdfReader, PdfWriter
from app.models.llm_ready_page import LLMPageInferenceResource
from app.config.settings import settings
from app.config.logging_config import logger
import base64
from botocore.exceptions import ClientError
import fitz  # PyMuPDF


class PDFExtractionService:
    """Service for extracting text and tables from PDF documents."""

    def __init__(self):
        """Initialize the PDF extraction service with AWS Textract."""
        self.textract = boto3.client(
            "textract",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )

    def _get_aws_error_info(self, error: ClientError) -> Tuple[str, str]:
        """Extract error code and message from AWS ClientError."""
        response = getattr(error, "response", {})
        error_dict = response.get("Error", {})
        return (error_dict.get("Code", "UnknownError"), error_dict.get("Message", str(error)))

    def _check_pdf_header(self, pdf_bytes: bytes) -> bool:
        """Check if file starts with PDF header."""
        return pdf_bytes.startswith(b"%PDF-")

    def _convert_pdf_to_images(self, pdf_bytes: bytes) -> bytes:
        """Convert PDF to images and back to PDF for Textract compatibility."""
        try:
            # Open PDF with PyMuPDF
            pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
            output_pdf = fitz.open()  # New PDF for storing images

            logger.info(f"Converting PDF with {len(pdf_document)} pages")

            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                # Convert page to image with higher resolution
                zoom = 2.0  # Increase resolution
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat, alpha=False)

                # Create a new page with same dimensions
                rect = page.rect
                new_page = output_pdf.new_page(width=rect.width, height=rect.height)

                # Convert pixmap to image and insert into new page
                img_rect = fitz.Rect(0, 0, rect.width, rect.height)
                new_page.insert_image(img_rect, pixmap=pix)

                if page_num % 10 == 0:  # Log progress every 10 pages
                    logger.info(f"Converted page {page_num + 1}/{len(pdf_document)}")

            # Save the new PDF to bytes
            output_stream = BytesIO()
            output_pdf.save(output_stream, garbage=4, deflate=True, clean=True)
            output_stream.seek(0)
            converted_bytes = output_stream.read()

            # Clean up
            pdf_document.close()
            output_pdf.close()

            logger.info("Successfully converted PDF to image-based format")
            return converted_bytes
        except Exception as e:
            logger.error(f"Error converting PDF: {str(e)}")
            return pdf_bytes

    async def extract_tables_and_text_from_file(
        self, pdf_bytes: bytes, keep_document_open: bool = False
    ) -> Tuple[list[LLMPageInferenceResource], bytes]:
        """Extract both text and tables from a PDF document."""
        # Log file details
        file_size = len(pdf_bytes) / 1024  # size in KB
        is_valid_pdf = self._check_pdf_header(pdf_bytes)
        logger.info(f"Processing PDF - Size: {file_size:.2f}KB, Valid PDF Header: {is_valid_pdf}")

        if not is_valid_pdf:
            logger.warning("File does not appear to be a valid PDF (missing PDF header)")
            sample = base64.b64encode(pdf_bytes[:100]).decode("utf-8")
            logger.debug(f"First 100 bytes (base64): {sample}")

        # Extract text using PyPDF2
        pdf_file = BytesIO(pdf_bytes)
        pdf_reader = PdfReader(pdf_file)
        logger.info(f"PDF has {len(pdf_reader.pages)} pages")

        # Prepare list for inference results
        inference_result_resources: List[LLMPageInferenceResource] = []

        # Process each page for text extraction
        total_text_length = 0
        for page_number in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_number]
            page_inference_resource = LLMPageInferenceResource()
            page_inference_resource.page_number = page_number

            # Extract text from page
            extracted_text = page.extract_text()
            total_text_length += len(extracted_text)
            page_inference_resource.given_text = extracted_text
            logger.info(f"Page {page_number + 1}: Extracted {len(extracted_text)} characters of text")
            inference_result_resources.append(page_inference_resource)

        logger.info(f"Total extracted text length: {total_text_length} characters")

        # Attempt table extraction only if text extraction was successful
        try:
            # Check if the PDF is scanned/image-based or searchable
            first_page = pdf_reader.pages[0]
            first_page_text = first_page.extract_text().strip()
            logger.info(f"First page text length: {len(first_page_text)} characters")

            if first_page_text:  # Only attempt table extraction if text was found
                logger.info("PDF appears to be text-based, attempting table extraction")
                # Extract tables
                extracted_tables = await self.extract_tables_and_check_time(pdf_bytes)

                # Add tables to the corresponding pages if found
                for page_number in range(len(pdf_reader.pages)):
                    if page_number + 1 in extracted_tables:  # Textract uses 1-based page numbers
                        inference_result_resources[page_number].given_tables = extracted_tables[page_number + 1]
                        logger.info(f"Added {len(extracted_tables[page_number + 1])} tables to page {page_number + 1}")
            else:
                logger.warning("PDF appears to be scanned/image-based, skipping table extraction")
        except Exception as e:
            logger.error(f"Table extraction error: {str(e)}")
            # Log a sample of the PDF content for debugging
            sample = base64.b64encode(pdf_bytes[:100]).decode("utf-8")
            logger.debug(f"First 100 bytes of PDF (base64): {sample}")

        return inference_result_resources, pdf_bytes

    async def process_multiple_pdfs(self, pdf_bytes_list: List[bytes]) -> Tuple[list[LLMPageInferenceResource], bytes]:
        """Process multiple PDFs and combine their content."""
        all_resources: List[LLMPageInferenceResource] = []
        page_offset = 0

        logger.info(f"Processing {len(pdf_bytes_list)} PDFs")

        # Process each PDF separately first
        for index, pdf_bytes in enumerate(pdf_bytes_list, 1):
            try:
                logger.info(f"Processing PDF {index} of {len(pdf_bytes_list)}")
                # Extract text and attempt table extraction for each PDF individually
                resources, _ = await self.extract_tables_and_text_from_file(pdf_bytes)

                # Adjust page numbers
                for resource in resources:
                    if resource.page_number is not None:
                        resource.page_number = resource.page_number + page_offset
                    all_resources.append(resource)

                # Update offset for next PDF
                pdf_file = BytesIO(pdf_bytes)
                pdf_reader = PdfReader(pdf_file)
                page_offset += len(pdf_reader.pages)
                logger.info(f"Successfully processed PDF {index}")
            except Exception as e:
                logger.error(f"Error processing PDF {index}: {str(e)}")
                continue

        # Then concatenate PDFs for storage
        concatenated_pdf = await self.concatenate_pdfs(pdf_bytes_list)
        logger.info(f"Concatenated {len(pdf_bytes_list)} PDFs, total pages: {page_offset}")

        return all_resources, concatenated_pdf

    async def concatenate_pdfs(self, pdf_bytes_list: List[bytes]) -> bytes:
        """Concatenate multiple PDFs into a single PDF."""
        merger = PdfWriter()

        # Add each PDF to the merger
        for index, pdf_bytes in enumerate(pdf_bytes_list, 1):
            try:
                pdf_file = BytesIO(pdf_bytes)
                pdf_reader = PdfReader(pdf_file)
                for page in pdf_reader.pages:
                    merger.add_page(page)
                logger.info(f"Added PDF {index} to merger ({len(pdf_reader.pages)} pages)")
            except Exception as e:
                logger.error(f"Error adding PDF {index} to merger: {str(e)}")

        # Write the merged PDF to bytes
        output = BytesIO()
        merger.write(output)
        output.seek(0)
        return output.read()

    async def get_tables_for_each_page_formatted_as_text(
        self,
        pdf_bytes: bytes,
    ) -> Tuple[Dict[int, List[str]], bytes]:
        """Extract tables from PDF using AWS Textract."""
        try:
            # Validate PDF size (AWS Textract has a 500MB limit)
            file_size_mb = len(pdf_bytes) / (1024 * 1024)
            logger.info(f"Checking file size for Textract: {file_size_mb:.2f}MB")

            if file_size_mb > 500:
                logger.warning("PDF file too large for table extraction")
                return {}, pdf_bytes

            # Log attempt to call Textract
            logger.info("Calling AWS Textract for table extraction")
            try:
                # First attempt with original PDF
                response = self.textract.analyze_document(Document={"Bytes": pdf_bytes}, FeatureTypes=["TABLES"])
                logger.info(f"Textract response received, processing {len(response.get('Blocks', []))} blocks")
            except ClientError as e:
                error_code, error_message = self._get_aws_error_info(e)
                logger.error(f"AWS Textract error: {error_code} - {error_message}")
                if error_code == "UnsupportedDocumentException":
                    logger.info("Document format not supported, attempting conversion")
                    # Convert PDF to image-based format
                    converted_pdf = self._convert_pdf_to_images(pdf_bytes)
                    try:
                        response = self.textract.analyze_document(Document={"Bytes": converted_pdf}, FeatureTypes=["TABLES"])
                        logger.info("Successfully processed converted PDF")
                    except ClientError as e2:
                        logger.error(f"Failed to process converted PDF: {str(e2)}")
                        return {}, pdf_bytes
                else:
                    return {}, pdf_bytes

            # Process tables from response
            tables_with_pages: Dict[int, List[str]] = {}

            # Extract tables from blocks
            current_table = []
            current_page = 1
            table_count = 0

            for block in response["Blocks"]:
                if block["BlockType"] == "TABLE":
                    current_table = []
                    table_count += 1
                elif block["BlockType"] == "CELL" and "Text" in block:
                    current_table.append(block["Text"])
                elif block["BlockType"] == "TABLE_END":
                    if current_table:
                        if current_page not in tables_with_pages:
                            tables_with_pages[current_page] = []
                        tables_with_pages[current_page].append("\n".join(current_table))
                    current_table = []

            logger.info(f"Extracted {table_count} tables across {len(tables_with_pages)} pages")
            return tables_with_pages, pdf_bytes
        except Exception as e:
            logger.error(f"Table extraction error: {str(e)}")
            return {}, pdf_bytes

    async def extract_tables_and_check_time(self, pdf_bytes: bytes) -> Dict[int, List[str]]:
        """Extract tables while measuring and reporting processing times."""
        import time

        # Start timing
        start = time.time()

        # Extract tables and format them
        tables_for_pages, _ = await self.get_tables_for_each_page_formatted_as_text(pdf_bytes)

        # Calculate processing time
        end_detect_and_format = time.time()
        processing_time = end_detect_and_format - start

        # Print timing statistics
        logger.info(f"Table extraction completed in {processing_time:.3f}s")
        logger.info(f"Found tables on {len(tables_for_pages)} pages")

        return tables_for_pages


def get_pdf_extraction_service() -> PDFExtractionService:
    """Factory function to create a PDFExtractionService instance."""
    return PDFExtractionService()
