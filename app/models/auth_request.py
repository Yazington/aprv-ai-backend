from typing import Optional

from pydantic import BaseModel, Field, validator


class AuthRequest(BaseModel):
    """Pydantic model representing authentication request data.

    This model is used to validate and structure incoming authentication data
    from API requests. The auth_token is required for Google OAuth authentication.
    """

    auth_token: str = Field(
        ...,  # This makes the field required
        description="Google OAuth ID token from Google Sign-In",
        min_length=50,  # Google tokens are typically much longer
    )

    access_token: Optional[str] = Field(
        None,
        description="JWT token for API authorization",
    )

    @validator("auth_token")
    def validate_auth_token(cls, v):
        """Validate the auth token format"""
        if not v or len(v.strip()) < 50:
            raise ValueError("Invalid Google auth token format")
        return v.strip()
