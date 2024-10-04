from typing import Optional

from pydantic import BaseModel


class CreatePromptRequest(BaseModel):
    prompt: str
    conversation_id: Optional[str] = None
