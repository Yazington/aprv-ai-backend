from datetime import datetime
from typing import Optional

from beanie import Document, Indexed, PydanticObjectId


class Review(Document):
    conversation_id: PydanticObjectId
    page_number: Optional[int] = None
    review_description: Optional[str] = None
    guideline_achieved: Optional[bool] = None
    created_at: datetime = datetime.utcnow()
    modified_at: datetime = datetime.utcnow()

    class Settings:
        name = "reviews"
        indexes = [
            [
                ("conversation_id", 1),
                ("created_at", 1),
                ("modified_at", 1)
            ]
        ]
