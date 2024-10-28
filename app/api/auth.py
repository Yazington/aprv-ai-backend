import datetime
from typing import Annotated

import jwt

# from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.config.logging_config import logger
from app.config.settings import settings
from app.models.auth_request import AuthRequest
from app.models.users import GoogleAuthInfo, User
from app.services.mongo_service import MongoService, get_mongo_service

router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
)


@router.post("/google")
async def auth_google(auth_request: AuthRequest, mongo_service: Annotated[MongoService, Depends(get_mongo_service)]):
    """
    Authenticate and gives access token
    """
    if not settings.aprv_ai_api_key:
        raise Exception("aprv_ai_api_key not set!")

    if not auth_request.access_token:
        print("access_token unavailable")
    # Print the token for debugging purposes
    # logging.info(auth_request.token[:-20])

    # Verify the ID token using Google's API
    idinfo = id_token.verify_oauth2_token(auth_request.auth_token, google_requests.Request(), settings.google_client_id)

    # Check if the token is from the correct issuer
    if idinfo["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
        raise HTTPException(status_code=401, detail="Wrong issuer")

    # Extract user info from the token
    email = idinfo.get("email")
    if not idinfo.get("email_verified"):
        raise HTTPException(status_code=401, detail="Email not verified by Google")
    logger.info(email)
    google_auth_info_instance = GoogleAuthInfo(**idinfo)

    # Check if the user already exists in the database
    existing_user = await mongo_service.engine.find_one(User, {"email": email})

    user_id = None

    if not existing_user:
        new_user_data = {"email": email, "google_auth": google_auth_info_instance.dict()}
        new_user = User(**new_user_data)

        # Generate JWT token
        expiration_time = datetime.datetime.utcnow() + datetime.timedelta(days=1)  # Token expires in 1 hour
        jwt_payload = {"email": email, "exp": expiration_time.timestamp(), "user_id": str(new_user.id)}
        access_token = jwt.encode(jwt_payload, settings.aprv_ai_api_key, algorithm="HS256")

        new_user.current_access_token = access_token
        await mongo_service.engine.save(new_user)
        user_id = new_user.id
    else:
        # Update the existing user's info
        existing_user.google_auth = google_auth_info_instance.dict()
        existing_user.modified_at = datetime.datetime.utcnow()

        # Generate JWT token
        expiration_time = datetime.datetime.utcnow() + datetime.timedelta(days=1)  # Token expires in 1 hour
        jwt_payload = {"email": email, "exp": expiration_time.timestamp(), "user_id": str(existing_user.id)}
        access_token = jwt.encode(jwt_payload, settings.aprv_ai_api_key, algorithm="HS256")

        existing_user.current_access_token = access_token
        await mongo_service.engine.save(existing_user)
        user_id = existing_user.id

    return {
        "message": "User authenticated",
        "user_email": email,
        "access_token": access_token,
        "exp": expiration_time.timestamp(),
        "user_id": str(user_id),
    }
