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
        return f"""
        \npage number: {self.page_number}\n
        text of {self.page_number}:{self.given_text}\n
        tables of {self.page_number}:{tables_text}\n
        RESULT OF DESIGN AGAINST THE TEXT OF PAGE {self.page_number}:{infer_response}\n
        RESULT OF WETHER OR NOT DESIGN RESPECTS PAGE {self.page_number}:{review_achieved}\n"""
