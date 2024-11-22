import os
from typing import Dict, List, Tuple

import fitz  # type:ignore
from gmft.pdf_bindings import PyPDFium2Document
from torch import device  # type: ignore

from app.models.llm_ready_page import LLMPageInferenceResource

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"  # Disable CUDA


class PDFExtractionService:
    def __init__(self):
        pass

    async def extract_tables_and_text_from_file(
        self, pdf_bytes, keep_document_open=False
    ) -> Tuple[list[LLMPageInferenceResource], fitz.Document]:
        extracted_tables = await self.extract_tables_and_check_time(pdf_bytes)
        pdf_document = fitz.open("pdf", pdf_bytes)
        inference_result_resources: List[LLMPageInferenceResource] = []  # type:ignore
        for page_number in range(pdf_document.page_count):
            page = pdf_document[page_number]
            page_inference_resource = LLMPageInferenceResource()
            page_inference_resource.page_number = page_number
            page_inference_resource.given_text = page.get_text()
            if page_number in extracted_tables.keys():
                page_inference_resource.given_tables = extracted_tables[page_number]
            inference_result_resources.append(page_inference_resource)
        if not keep_document_open:
            pdf_document.close()
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


def get_pdf_extraction_service():
    return PDFExtractionService()
