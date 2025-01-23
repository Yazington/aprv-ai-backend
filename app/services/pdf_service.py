import io
import os
from typing import Annotated, AsyncGenerator, Dict, List, Tuple

import fitz  # type:ignore
import PyPDF2
from fastapi import Depends
from gmft.pdf_bindings import PyPDFium2Document  #type:ignore
from odmantic import ObjectId

from app.services.mongo_service import MongoService, get_mongo_service  #type:ignore

os.environ["TORCH_DEVICE"] = "cpu"
from app.models.llm_ready_page import LLMPageInferenceResource

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"  # Disable CUDA


class PDFService:
    CHUNK_SIZE = 1024 * 1024  # 1MB chunks

    def __init__(self, mongo_service: MongoService):
        self.mongo_service = mongo_service

    async def combine_guidelines(
        self, *gridfs_file_ids: ObjectId
    ) -> AsyncGenerator[bytes, None]:
        pdf_writer = PyPDF2.PdfWriter()

        for file_id in gridfs_file_ids:
            grid_out = await self.mongo_service.async_fs.open_download_stream(file_id)
            if not grid_out:
                raise ValueError(f"File {file_id} not found")

            # Read PDF content into a buffer
            pdf_buffer = io.BytesIO()
            while True:
                chunk = await grid_out.read(self.CHUNK_SIZE)
                if not chunk:
                    break
                pdf_buffer.write(chunk)
            pdf_buffer.seek(0)

            # Add all pages to the writer
            pdf_reader = PyPDF2.PdfReader(pdf_buffer)
            for page in pdf_reader.pages:
                pdf_writer.add_page(page)
            pdf_buffer.close()

        # Write merged PDF to output buffer
        output_buffer = io.BytesIO()
        pdf_writer.write(output_buffer)
        output_buffer.seek(0)

        # Stream merged content in chunks
        while True:
            chunk = output_buffer.read(self.CHUNK_SIZE)
            if not chunk:
                break
            yield chunk

        output_buffer.close()

    async def extract_tables_and_text_from_file(
        self, pdf_bytes, keep_document_open=False
    ) -> Tuple[list[LLMPageInferenceResource], fitz.Document]:
        print("Starting table extraction process...")
        try:
            extracted_tables = await self.extract_tables_and_check_time(pdf_bytes)
            print(f"Tables extracted successfully. Found tables on {len(extracted_tables)} pages")
        except Exception as e:
            print(f"Error during table extraction: {str(e)}")
            raise

        print("Opening PDF document with fitz...")
        try:
            pdf_document = fitz.open("pdf", pdf_bytes)
            print(f"PDF document opened successfully. Total pages: {pdf_document.page_count}")
        except Exception as e:
            print(f"Error opening PDF document: {str(e)}")
            raise

        inference_result_resources: List[LLMPageInferenceResource] = []
        print("Starting page-by-page extraction...")

        for page_number in range(pdf_document.page_count):
            print(f"Processing page {page_number + 1}/{pdf_document.page_count}")
            try:
                page = pdf_document[page_number]
                page_inference_resource = LLMPageInferenceResource()
                page_inference_resource.page_number = page_number

                print(f"Extracting text from page {page_number + 1}...")
                page_inference_resource.given_text = page.get_text()
                # print(f"Text extracted from page {page_number + 1}, length: {len(page_inference_resource.given_text)} characters")

                if page_number in extracted_tables:
                    print(f"Found {len(extracted_tables[page_number])} tables on page {page_number + 1}")
                    page_inference_resource.given_tables = extracted_tables[page_number]
                else:
                    print(f"No tables found on page {page_number + 1}")

                inference_result_resources.append(page_inference_resource)
            except Exception as e:
                print(f"Error processing page {page_number + 1}: {str(e)}")
                raise

        if not keep_document_open:
            print("Closing PDF document...")
            pdf_document.close()
            print("PDF document closed successfully")
        else:
            print("Keeping PDF document open as requested")

        print(f"Processing completed. Processed {len(inference_result_resources)} pages total")
        return inference_result_resources, pdf_document

    async def get_tables_for_each_page_formatted_as_text(
        self,
        pdf_bytes: bytes,
    ) -> Tuple[Dict[int, List[str]], PyPDFium2Document]:
        from gmft.auto import AutoFormatConfig, AutoTableFormatter, TableDetector, TATRDetectorConfig  # type:ignore

        config = TATRDetectorConfig()
        config.torch_device = "cpu"
        detector = TableDetector(config=config)

        config = AutoFormatConfig()
        config.torch_device = "cpu"
        config.semantic_spanning_cells = True  # [Experimental] better spanning cells
        config.enable_multi_header = True  # multi-indices

        formatter = AutoTableFormatter(config)

        doc = PyPDFium2Document(pdf_bytes)
        tables_with_pages: Dict[int, List[str]] = {}
        for page_number, page in enumerate(doc, start=1):
            extracted_tables = detector.extract(page)
            for table in extracted_tables:
                formatted_table = formatter.extract(table)
                try:
                    if page_number not in tables_with_pages.keys():
                        tables_with_pages[page_number] = [formatted_table.df().to_string(index=False)]
                    else:
                        tables_with_pages[page_number] = [*tables_with_pages[page_number], formatted_table.df().to_string(index=False)]
                except Exception as e:
                    print(e)
                    tables_with_pages[page_number] = []

        return tables_with_pages, doc

    async def extract_tables_and_check_time(self, pdf_bytes):
        import time

        _total_detect_time = 0.0
        _total_detect_num = 0.0
        _total_format_time = 0.0
        _total_format_num = 0.0

        start = time.time()
        tables_for_pages, doc = await self.get_tables_for_each_page_formatted_as_text(pdf_bytes)

        num_pages = len(doc)
        end_detect_and_format = time.time()

        print(f"\nDetect time: {end_detect_and_format - start:.3f}s for {num_pages} pages")
        _total_detect_time += end_detect_and_format - start
        _total_detect_num += num_pages
        _total_format_num += len(tables_for_pages)
        if _total_format_num > 0:
            print(f"Macro: {_total_detect_time/_total_detect_num:.3f} s/page and {_total_format_time/_total_format_num:.3f} s/table.")
        if _total_detect_num > 0:
            print(f"Total: {(_total_detect_time+_total_format_num)/(_total_detect_num)} s/page")
        doc.close()
        print(f"Paper: \nDetect time: {end_detect_and_format - start:.3f}s for {num_pages} pages")

        _total_detect_time = end_detect_and_format - start
        _total_detect_num = num_pages
        _total_format_num = len(tables_for_pages)
        if _total_detect_num > 0:
            print(f"Total: {(_total_detect_time + _total_format_num) / _total_detect_num} s/page")
        return tables_for_pages


def get_pdf_service(mongo_service: Annotated[MongoService, Depends(get_mongo_service)]):
    return PDFService(mongo_service)
