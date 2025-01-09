from typing import Optional

from pydantic import BaseModel


class AuthRequest(BaseModel):
    """Pydantic model representing authentication request data.

    This model is used to validate and structure incoming authentication data
    from API requests. Both fields are optional to support different auth flows.
    """

    auth_token: Optional[str] = None
    # Used for Google OAuth token authentication
    # Typically contains the ID token from Google Sign-In

    access_token: Optional[str] = None
    # Used for API access token authentication
    # Typically contains a JWT token for API authorization
