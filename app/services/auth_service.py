# Authentication service handling JWT token generation and Google OAuth verification
import datetime
from typing import Annotated, Any, Dict, Tuple

import jwt
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from fastapi import Depends, HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.config.logging_config import logger
from app.config.settings import settings
from app.models.users import User
from app.services.mongo_service import MongoService, get_mongo_service


class AuthService:
    """Main authentication service class handling token operations"""

    def __init__(self, mongo_service: MongoService):
        """Initialize with MongoDB service dependency"""
        self.mongo_service = mongo_service

    async def generate_access_token(self, user: User) -> Tuple[str, datetime.datetime]:
        """
        Generates a JWT access token for the given user
        Args:
            user: User object containing email and id
        Returns:
            Tuple containing the JWT token and its expiration time
        """
        # Set token expiration to 1 day from now
        expiration_time = datetime.datetime.utcnow() + datetime.timedelta(days=1)

        # Create JWT payload with user info and expiration
        jwt_payload = {"email": user.email, "exp": expiration_time.timestamp(), "user_id": str(user.id)}

        # Verify API key is configured
        if not settings.aprv_ai_api_key:
            logger.error("APRV API KEY NOT SET!")
            raise HTTPException(status_code=500, detail="Failed to authenticate")

        # Generate and return signed JWT token
        return jwt.encode(jwt_payload, settings.aprv_ai_api_key, algorithm="HS256"), expiration_time

    async def verify_google_token(self, token: str) -> Dict[str, Any]:
        """
        Verifies a Google OAuth2 token and returns token info
        Args:
            token: Google OAuth token string
        Returns:
            Dictionary containing verified token information
        Raises:
            HTTPException: If token verification fails
        """
        try:
            logger.info("Starting Google token verification")

            # Verify Google client ID is configured
            if not settings.google_client_id:
                logger.error("Google client ID not configured")
                raise HTTPException(status_code=500, detail="Google authentication not properly configured")

            # Basic token validation
            if not token or len(token) < 50:  # Google tokens are typically much longer
                logger.error("Invalid token format")
                raise HTTPException(status_code=400, detail="Invalid token format")

            # Log detailed debugging information
            logger.info(f"Token length: {len(token)}")
            logger.info(f"Token prefix: {token[:20]}...")  # Log first 20 chars
            logger.info(f"Using client ID: {settings.google_client_id}")

            # Configure request with retries
            retry_strategy = Retry(
                total=1,  # Only retry once
                backoff_factor=0.5,
                status_forcelist=[500, 502, 503, 504],
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)

            # Create custom request object with retry strategy
            class TimeoutRequest(google_requests.Request):
                def __init__(self):
                    super().__init__()
                    self.session.mount("https://", adapter)

                def __call__(self, url, method="GET", **kwargs):
                    kwargs.setdefault("timeout", (5, 10))  # 5 seconds connect, 10 seconds read
                    return super().__call__(url, method=method, **kwargs)

            request = TimeoutRequest()
            logger.info("Created request object with retry strategy and timeouts")

            # Attempt token verification with timeout
            logger.info("Starting token verification...")
            try:
                result = id_token.verify_oauth2_token(token, request, settings.google_client_id, clock_skew_in_seconds=10)
                logger.info("Token verification completed")
                logger.info("Google token verification successful")
                logger.info(f"Token verified for email: {result.get('email', 'email not found')}")
                return result
            except ValueError as ve:
                logger.error(f"Invalid token structure: {str(ve)}")
                raise HTTPException(status_code=400, detail=f"Invalid token structure: {str(ve)}") from None
            except requests.exceptions.RequestException as re:
                logger.error(f"Network error during verification: {str(re)}")
                raise HTTPException(status_code=503, detail="Unable to verify token due to network issues") from None
            except Exception as e:
                logger.error(f"Unexpected error during verification: {str(e)}")
                raise HTTPException(status_code=500, detail="Token verification failed unexpectedly") from e
        except Exception as e:
            logger.error(f"Token verification failed: {str(e)}")
            raise HTTPException(status_code=401, detail=f"Token verification failed: {str(e)}") from e


def get_auth_service(mongo_service: Annotated[MongoService, Depends(get_mongo_service)]) -> AuthService:
    """Dependency injection helper for AuthService"""
    return AuthService(mongo_service=mongo_service)
