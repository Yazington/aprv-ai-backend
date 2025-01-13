from typing import Optional

from odmantic import Model
from pydantic import BaseModel


class CreatePromptRequest(Model):
    prompt: str
    conversation_id: Optional[str] = None
