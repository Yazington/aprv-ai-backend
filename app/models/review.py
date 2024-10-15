from datetime import datetime
from enum import Enum
from typing import Optional

from odmantic import Field, Index, Model, ObjectId
from odmantic.query import asc


class Review(Model):
    conversation_id: ObjectId
    review_description: Optional[str] = None
    guideline_achieved: Optional[bool] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    modified_at: datetime = Field(default_factory=datetime.utcnow)
    model_config = {"indexes": lambda: [Index(asc(Review.conversation_id), asc(Review.created_at), asc(Review.modified_at))]}  # type: ignore
