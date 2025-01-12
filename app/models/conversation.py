from datetime import datetime
from typing import List, Optional

from beanie import Document, Indexed, PydanticObjectId


class Conversation(Document):
    all_messages_ids: List[PydanticObjectId] = []  # List of message IDs
    user_id: PydanticObjectId
    guidelines_ids: List[PydanticObjectId] = []
    design_id: Optional[PydanticObjectId] = None
    design_process_task_id: Optional[PydanticObjectId] = None
    thumbnail_text: Optional[str] = "Empty Conversation"
    created_at: datetime = datetime.utcnow()
    modified_at: datetime = datetime.utcnow()

    class Settings:
        name = "conversations"
        indexes = [
            [
                ("user_id", 1),
                ("created_at", 1),
                ("modified_at", 1)
            ]
        ]

    class Config:
        json_encoders = {
            PydanticObjectId: str
        }
