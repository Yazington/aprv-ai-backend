from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.models.auth_request import AuthRequest
from app.models.users import GoogleAuthInfo
from app.services.auth_service import AuthService, get_auth_service
from app.services.user_service import UserService, get_user_service

# Create API router for authentication endpoints
router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/google")
async def auth_google(
    auth_request: AuthRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    user_service: Annotated[UserService, Depends(get_user_service)],
):
    """Authenticate user via Google OAuth and return access token."""
    # Extract auth token from request
    auth_token = auth_request.auth_token
    if not auth_token:
        raise HTTPException(status_code=400, detail="Auth token is required")

    # Verify Google token and get token info
    token_info = await auth_service.verify_google_token(auth_token)

    # Validate token issuer (must be from Google)
    if token_info["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
        raise HTTPException(status_code=401, detail="Wrong issuer")

    # Get and validate email from token
    email: str | None = token_info.get("email")
    if not token_info.get("email_verified") or not email:
        raise HTTPException(status_code=401, detail="Email not verified by Google")

    # Create GoogleAuthInfo instance from token data
    google_auth_info_instance = GoogleAuthInfo(**token_info)

    # Get or create user in database
    user = await user_service.get_or_create_user(email, google_auth_info_instance)

    # Generate access token for the user
    access_token, expiration_time = await auth_service.generate_access_token(user)

    # Return authentication response
    return {
        "message": "User authenticated",
        "user_email": email,
        "access_token": access_token,
        "exp": expiration_time.timestamp(),
        "user_id": str(user.id),
    }
