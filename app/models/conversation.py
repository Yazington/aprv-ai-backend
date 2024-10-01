from datetime import datetime
from typing import List

from odmantic import Field, Model


class Conversation(Model):
    all_messages: List[str]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    modified_at: datetime = Field(default_factory=datetime.utcnow)
