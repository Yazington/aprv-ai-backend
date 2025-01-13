from typing import Optional
from odmantic import Model, Field, Index


class GoogleAuthInfo(Model):
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

    # @classmethod
    # def create(cls, idinfo):
    #     return cls(
    #         iss=idinfo.get("iss"),
    #         azp=idinfo.get("azp"),
    #         aud=idinfo.get("aud"),
    #         sub=idinfo.get("sub"),
    #         email=idinfo.get("email"),
    #         email_verified=idinfo.get("email_verified"),
    #         nbf=idinfo.get("nbf"),
    #         name=idinfo.get("name"),
    #         picture=idinfo.get("picture"),
    #         given_name=idinfo.get("given_name"),
    #         family_name=idinfo.get("family_name"),
    #         iat=idinfo.get("iat"),
    #         exp=idinfo.get("exp"),
    #         jti=idinfo.get("jti"),
    #     )


class User(Model):
    """User model for storing user information."""
    email: str = Field(index=True)
    given_name: str
    family_name: str
    picture: str
    refresh_token: Optional[str] = None
