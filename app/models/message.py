from datetime import datetime

from odmantic import Field, Model


class Message(Model):
    content: str
    is_from_human: bool
    created_at: datetime = Field(default_factory=datetime.utcnow)
    modified_at: datetime = Field(default_factory=datetime.utcnow)
