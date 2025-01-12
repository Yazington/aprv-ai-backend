from datetime import datetime
from typing import List, Optional

from beanie import Document, Indexed, PydanticObjectId


class Message(Document):
    conversation_id: PydanticObjectId
    content: str
    is_from_human: bool
    user_id: str
    uploaded_pdf_ids: List[str] = []  # Beanie uses str for IDs
    created_at: datetime = datetime.utcnow()
    modified_at: datetime = datetime.utcnow()

    class Settings:
        name = "messages"
        indexes = [
            [
                ("user_id", 1),
                ("conversation_id", 1),
                ("created_at", 1),
                ("modified_at", 1)
            ]
        ]

    class Config:
        json_encoders = {
            PydanticObjectId: str
        }
