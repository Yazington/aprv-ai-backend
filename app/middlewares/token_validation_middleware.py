import datetime
import logging
from typing import Union

import jwt
from config.settings import settings
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware


class TokenValidationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Bypass token validation for OPTIONS requests (CORS preflight requests)
        if request.method == "OPTIONS":
            return await call_next(request)

        if not settings.aprv_ai_api_key:
            raise Exception("aprv_ai_api_key not set!")

        # logging.info(request.url.path)

        # Skip token validation for specific paths if necessary
        if request.url.path == "/auth/google":
            return await call_next(request)

        # Extract the token from Authorization header or URL query parameter
        authorization: Union[str, None] = request.headers.get("Authorization")
        token: Union[str, None] = None

        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]  # Get the token part from the header
        else:
            # Try to get the token from query parameters
            token = request.query_params.get("access_token")

        if not token:
            raise HTTPException(status_code=401, detail="Invalid or missing token")

        try:
            # Decode and verify the JWT token
            payload = jwt.decode(token, settings.aprv_ai_api_key, algorithms=["HS256"])
            email = payload.get("email")
            exp = payload.get("exp")
            user_id = payload.get("user_id")

            if not email or not exp:
                raise HTTPException(status_code=401, detail="Invalid token payload")

            # Check if the token is expired
            if datetime.datetime.utcnow().timestamp() > exp:
                raise HTTPException(status_code=401, detail="Token has expired")

            # Save validated token info in request.state
            request.state.user_email = email
            request.state.user_id = user_id

            # Proceed if token is valid
            logging.info(f"Token valid for user: {email}")

        except jwt.ExpiredSignatureError:
            logging.error(f"Expired token for {email}")
            raise HTTPException(status_code=401, detail="Token has expired") from None
        except jwt.InvalidTokenError:
            logging.error(f"Invalid token {token}")
            raise HTTPException(status_code=401, detail="Invalid token") from None

        # Call the next middleware or route
        response = await call_next(request)
        return response
