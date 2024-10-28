from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.models.auth_request import AuthRequest
from app.models.users import GoogleAuthInfo
from app.services.auth_service import AuthService, get_auth_service
from app.services.user_service import UserService, get_user_service

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/google")
async def auth_google(
    auth_request: AuthRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    user_service: Annotated[UserService, Depends(get_user_service)],
):
    """Authenticate user via Google OAuth and return access token."""
    auth_token = auth_request.auth_token
    if not auth_token:
        raise HTTPException(status_code=400, detail="Auth token is required")

    token_info = await auth_service.verify_google_token(auth_token)

    if token_info["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
        raise HTTPException(status_code=401, detail="Wrong issuer")

    email: str | None = token_info.get("email")
    if not token_info.get("email_verified") or not email:
        raise HTTPException(status_code=401, detail="Email not verified by Google")

    google_auth_info_instance = GoogleAuthInfo(**token_info)
    user = await user_service.get_or_create_user(email, google_auth_info_instance)

    access_token, expiration_time = await auth_service.generate_access_token(user)

    return {
        "message": "User authenticated",
        "user_email": email,
        "access_token": access_token,
        "exp": expiration_time.timestamp(),
        "user_id": str(user.id),
    }
