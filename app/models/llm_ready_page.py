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
