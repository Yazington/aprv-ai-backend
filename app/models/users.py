from datetime import datetime
from typing import Optional

from odmantic import Field, Model


class User(Model):
    name: Optional[str]
    email: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    modified_at: datetime = Field(default_factory=datetime.utcnow)
