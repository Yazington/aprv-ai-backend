from typing import Any, List, Optional

from pydantic import BaseModel


class LLMPageRequest(BaseModel):
    page_number: Optional[int] = None
    given_text: Optional[Any] = None
    give_images: Optional[Any] = None
    given_tables: Optional[List[str]] = []


class BrandGuideline(BaseModel):
    review_description: Optional[str] = None
    guideline_achieved: Optional[bool] = None


class LLMPageInferenceResource(BaseModel):
    page_number: Optional[int] = None
    given_text: Optional[Any] = None
    given_tables: Optional[List[str]] = []
    inference_response: Optional[BrandGuideline] = None

    def __str__(self):
        tables_text = ""
        if self.given_tables and len(self.given_tables):
            tables_text = "\n".join(self.given_tables)
        infer_response = ""
        review_achieved = ""
        if self.inference_response:
            infer_response = self.inference_response.review_description
            review_achieved = self.inference_response.guideline_achieved
        return f"""\npage: {self.page_number}\ntext:{self.given_text}\ntables:{tables_text}\nreview of page against design description:{infer_response}\ndesign respects guideline:{review_achieved}\n"""
