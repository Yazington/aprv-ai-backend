from datetime import datetime
from enum import Enum
from typing import Optional
from odmantic import Model, Field, Index, ObjectId
from pydantic import BaseModel


class TaskStatus(Enum):
    IN_PROGRESS = 0
    COMPLETE = 1
    FAILED = 2


class Task(Model):
    conversation_id: Optional[ObjectId] = None  # Keep using ObjectId for MongoDB compatibility
    status: str
    generated_txt_id: Optional[ObjectId] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    modified_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "collection": "tasks",
        "indexes": lambda: [
            Index(Task.conversation_id, Task.created_at, Task.modified_at)
        ]
    }
