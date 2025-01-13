from datetime import datetime
from typing import List, Optional
from odmantic import Model, Field, Index, ObjectId
from pydantic import BaseModel


class Message(Model):
    conversation_id: ObjectId
    content: str
    is_from_human: bool
    user_id: str
    uploaded_pdf_ids: List[str] = Field(default_factory=list)  # Keep using str for IDs
    created_at: datetime = Field(default_factory=datetime.utcnow)
    modified_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "collection": "messages",
        "indexes": lambda: [
            Index(Message.user_id, Message.conversation_id, Message.created_at, Message.modified_at)
        ]
    }
