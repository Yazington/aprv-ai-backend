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
        # Join tables if they exist
        tables_text = "\n".join(self.given_tables) if self.given_tables else ""

        # Extract inference details if available
        infer_response = ""
        review_achieved = ""
        if self.inference_response:
            infer_response = self.inference_response.review_description or ""
            review_achieved = self.inference_response.guideline_achieved or ""

        # Return formatted string
        return (
            f"\npage number: {self.page_number or 'N/A'}\n"
            f"text of {self.page_number or 'N/A'}: {self.given_text or 'N/A'}\n"
            f"tables of {self.page_number or 'N/A'}:\n{tables_text}\n"
            f"RESULT OF DESIGN AGAINST THE TEXT OF PAGE {self.page_number or 'N/A'}: {infer_response}\n"
            f"RESULT OF WHETHER OR NOT DESIGN RESPECTS PAGE {self.page_number or 'N/A'}: {review_achieved}\n"
        )
