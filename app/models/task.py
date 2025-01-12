from datetime import datetime
from enum import Enum
from typing import Optional

from beanie import Document, Indexed, PydanticObjectId


class TaskStatus(Enum):
    IN_PROGRESS = 0
    COMPLETE = 1
    FAILED = 2


class Task(Document):
    conversation_id: Optional[PydanticObjectId] = None  # Make it optional
    status: str
    generated_txt_id: Optional[PydanticObjectId] = None
    created_at: datetime = datetime.utcnow()
    modified_at: datetime = datetime.utcnow()

    class Settings:
        name = "tasks"
        indexes = [
            [
                ("conversation_id", 1),
                ("created_at", 1),
                ("modified_at", 1)
            ]
        ]
