from datetime import datetime
from enum import Enum
from typing import Optional

from odmantic import Field, Index, Model, ObjectId
from odmantic.query import asc


class TaskStatus(Enum):
    IN_PROGRESS = 0
    COMPLETE = 1
    FAILED = 2


class Task(Model):
    conversation_id: Optional[ObjectId] = None  # Make it optional
    status: str
    generated_txt_id: Optional[ObjectId] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    modified_at: datetime = Field(default_factory=datetime.utcnow)
    model_config = {"indexes": lambda: [Index(asc(Task.conversation_id), asc(Task.created_at), asc(Task.modified_at))]}  # type: ignore
