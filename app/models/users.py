from datetime import datetime
from typing import List, Optional

from odmantic import Field, Index, Model, ObjectId
from odmantic.query import asc
from pydantic import BaseModel


class GoogleAuthInfo(BaseModel):
    iss: Optional[str] = None
    azp: Optional[str] = None
    aud: Optional[str] = None
    sub: Optional[str] = None
    email: Optional[str] = None
    email_verified: bool = False
    nbf: Optional[int] = None
    name: Optional[str] = None
    picture: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    iat: Optional[int] = None
    exp: Optional[int] = None
    jti: Optional[str] = None

    @classmethod
    def create(cls, idinfo):
        return cls(
            iss=idinfo.get("iss"),
            azp=idinfo.get("azp"),
            aud=idinfo.get("aud"),
            sub=idinfo.get("sub"),
            email=idinfo.get("email"),
            email_verified=idinfo.get("email_verified"),
            nbf=idinfo.get("nbf"),
            name=idinfo.get("name"),
            picture=idinfo.get("picture"),
            given_name=idinfo.get("given_name"),
            family_name=idinfo.get("family_name"),
            iat=idinfo.get("iat"),
            exp=idinfo.get("exp"),
            jti=idinfo.get("jti"),
        )


class User(Model):
    name: Optional[str] = None
    email: str
    all_conversations_ids: Optional[List[ObjectId]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    modified_at: datetime = Field(default_factory=datetime.utcnow)
    google_auth: GoogleAuthInfo
    current_access_token: Optional[str] = None
    model_config = {"indexes": lambda: [Index(asc(User.email), asc(User.created_at), asc(User.modified_at))]}  # type: ignore
