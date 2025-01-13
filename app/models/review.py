from datetime import datetime
from typing import Optional
from odmantic import Model, Field, Index, ObjectId
from pydantic import BaseModel


class Review(Model):
    conversation_id: ObjectId
    page_number: Optional[int] = None
    review_description: Optional[str] = None
    guideline_achieved: Optional[bool] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    modified_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "collection": "reviews",
        "indexes": lambda: [
            Index(Review.conversation_id, Review.created_at, Review.modified_at)
        ]
    }
