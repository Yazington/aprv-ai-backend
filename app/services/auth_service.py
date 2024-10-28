import datetime
from typing import Annotated, Any, Dict, Tuple

import jwt
from fastapi import Depends, HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.config.logging_config import logger
from app.config.settings import settings
from app.models.users import User
from app.services.mongo_service import MongoService, get_mongo_service


class AuthService:
    def __init__(self, mongo_service: MongoService):
        self.mongo_service = mongo_service

    async def generate_access_token(self, user: User) -> Tuple[str, datetime.datetime]:
        expiration_time = datetime.datetime.utcnow() + datetime.timedelta(days=1)
        jwt_payload = {"email": user.email, "exp": expiration_time.timestamp(), "user_id": str(user.id)}
        if not settings.aprv_ai_api_key:
            logger.error("APRV API KEY NOT SET!")
            raise HTTPException(status_code=500, detail="Failed to authenticate")
        return jwt.encode(jwt_payload, settings.aprv_ai_api_key, algorithm="HS256"), expiration_time

    async def verify_google_token(self, token: str) -> Dict[str, Any]:
        """Verifies a Google OAuth2 token and returns token info."""
        try:
            return id_token.verify_oauth2_token(token, google_requests.Request(), settings.google_client_id)
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            raise HTTPException(status_code=401, detail="Token verification failed") from e


def get_auth_service(mongo_service: Annotated[MongoService, Depends(get_mongo_service)]) -> AuthService:
    return AuthService(mongo_service=mongo_service)
