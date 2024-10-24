import datetime
from config.logging_config import logger
from typing import Union

import jwt
from config.settings import settings
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class TokenValidationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Bypass token validation for OPTIONS requests (CORS preflight requests)
        if request.method == "OPTIONS":
            return await call_next(request)

        if not settings.aprv_ai_api_key:
            raise Exception("aprv_ai_api_key not set!")

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
            return self._unauthorized_response()

        try:
            # Decode and verify the JWT token
            payload = jwt.decode(token, settings.aprv_ai_api_key, algorithms=["HS256"])
            email = payload.get("email")
            exp = payload.get("exp")
            user_id = payload.get("user_id")

            if not email or not exp:
                return self._unauthorized_response()

            # Check if the token is expired
            if exp and datetime.datetime.utcnow().timestamp() > exp:
                return self._unauthorized_response()

            # Save validated token info in request.state
            request.state.user_email = email
            request.state.user_id = user_id

            # Proceed if token is valid
            logger.info(f"Token valid for user: {email}")

        except jwt.ExpiredSignatureError:
            logger.error(f"Expired token for {email}")
            return self._unauthorized_response()
        except jwt.InvalidTokenError:
            logger.error(f"Invalid token {token}")
            return self._unauthorized_response()

        # Call the next middleware or route
        response = await call_next(request)
        return response

    def _unauthorized_response(self):
        return JSONResponse(
            content={"detail": "Token expired"},
            status_code=401,
            headers={
                "Access-Control-Allow-Origin": "*",  # Replace with your allowed origins
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Allow-Methods": "*",
                "Access-Control-Allow-Headers": "*",
            },
        )
