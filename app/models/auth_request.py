from typing import Optional

from pydantic import BaseModel


class AuthRequest(BaseModel):
    auth_token: Optional[str] = None
    access_token: Optional[str] = None
