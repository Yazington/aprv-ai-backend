from datetime import datetime
from typing import Optional

from odmantic import Field, Model


class Document(Model):
    name: Optional[str]
    fs_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    modified_at: datetime = Field(default_factory=datetime.utcnow)
