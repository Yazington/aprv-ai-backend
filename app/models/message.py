from datetime import datetime
from typing import Optional

from odmantic import Field, Index, Model, ObjectId
from odmantic.query import asc


class Message(Model):
    conversation_id: ObjectId
    content: str
    is_from_human: bool
    user_id: ObjectId
    uploaded_pdf_ids: list[ObjectId] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    modified_at: datetime = Field(default_factory=datetime.utcnow)
    model_config = {
        "indexes": lambda: [Index(asc(Message.user_id), asc(Message.conversation_id), asc(Message.created_at), asc(Message.modified_at))]
    }  # type: ignore
