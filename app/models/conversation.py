from datetime import datetime
from typing import List, Optional
from odmantic import Model, Field, Index, ObjectId
from pydantic import BaseModel


class Conversation(Model):
    all_messages_ids: List[ObjectId] = Field(default_factory=list)  # List of message IDs
    user_id: ObjectId
    guidelines_ids: List[ObjectId] = Field(default_factory=list)
    design_id: Optional[ObjectId] = None
    design_process_task_id: Optional[ObjectId] = None
    thumbnail_text: str = Field(default="Empty Conversation")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    modified_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "collection": "conversations",
        "indexes": lambda: [
            Index(Conversation.user_id, Conversation.created_at, Conversation.modified_at)
        ]
    }
