from datetime import datetime

from odmantic import Field, Model


class Document(Model):
    name: str
    aws_object_path: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    modified_at: datetime = Field(default_factory=datetime.utcnow)
