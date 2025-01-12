from datetime import datetime
from typing import List, Optional

from odmantic import Field, Index, Model, ObjectId
from odmantic.query import asc


class Conversation(Model):
    all_messages_ids: List[ObjectId] = Field(default_factory=list)
    user_id: ObjectId
    guidelines_ids: List[ObjectId] = Field(default_factory=list)
    design_id: Optional[ObjectId] = None
    design_process_task_id: Optional[ObjectId] = None
    thumbnail_text: Optional[str] = "Empty Conversation"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    modified_at: datetime = Field(default_factory=datetime.utcnow)
    model_config = {"indexes": lambda: [Index(asc(Conversation.user_id), asc(Conversation.created_at), asc(Conversation.modified_at))]}  # type: ignore
