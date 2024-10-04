from datetime import datetime
from typing import List

from odmantic import Field, Model, ObjectId


class Conversation(Model):
    all_messages_ids: List[ObjectId] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    modified_at: datetime = Field(default_factory=datetime.utcnow)
