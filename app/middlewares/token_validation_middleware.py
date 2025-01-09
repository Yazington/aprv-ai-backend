import datetime
from typing import Union

import jwt
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config.logging_config import logger
from app.config.settings import settings


# This middleware class is responsible for validating JWT tokens in incoming requests.
class TokenValidationMiddleware(BaseHTTPMiddleware):
    # The dispatch method is called for each request. It validates the token and decides whether to proceed or return an error.
    async def dispatch(self, request: Request, call_next):
        # Bypass token validation for OPTIONS requests (CORS preflight requests)
        # Allow OPTIONS requests to pass through without token validation (used for CORS preflight requests).
        if request.method == "OPTIONS":
            return await call_next(request)

        # Ensure the API key is set in the settings; raise an exception if not.
        if not settings.aprv_ai_api_key:
            raise Exception("aprv_ai_api_key not set!")

        # Skip token validation for specific paths if necessary
        # Skip token validation for the Google authentication endpoint.
        if request.url.path == "/auth/google":
            return await call_next(request)

        # Extract the token from Authorization header or URL query parameter
        # Attempt to extract the token from the Authorization header or query parameters.
        authorization: Union[str, None] = request.headers.get("Authorization")
        token: Union[str, None] = None

        if authorization and authorization.startswith("Bearer "):
            # Extract the token part from the Authorization header.
            token = authorization.split(" ")[1]
        else:
            # If not found in the header, try to get the token from query parameters.
            token = request.query_params.get("access_token")

        if not token:
            # Return an unauthorized response if no token is found.
            return self._unauthorized_response()

        try:
            # Decode and verify the JWT token using the API key and HS256 algorithm.
            payload = jwt.decode(token, settings.aprv_ai_api_key, algorithms=["HS256"])
            email = payload.get("email")
            exp = payload.get("exp")
            user_id = payload.get("user_id")

            # Ensure the token contains email and expiration claims.
            if not email or not exp:
                return self._unauthorized_response()

            # Check if the token is expired by comparing the current time with the expiration time.
            if exp and datetime.datetime.utcnow().timestamp() > exp:
                return self._unauthorized_response()

            # Save validated token information in the request state for later use.
            request.state.user_email = email
            request.state.user_id = user_id

            # Log and proceed with the request if the token is valid.
            logger.info(f"Token valid for user: {email}")

        except jwt.ExpiredSignatureError:
            # Handle expired token error and log the incident.
            logger.error(f"Expired token for {email}")
            return self._unauthorized_response()
        except jwt.InvalidTokenError:
            # Handle invalid token error and log the incident.
            logger.error(f"Invalid token {token}")
            return self._unauthorized_response()

        # Call the next middleware or route handler in the chain.
        response = await call_next(request)
        return response

    def _unauthorized_response(self):
        # Return a JSON response indicating the token is expired or invalid, with appropriate CORS headers.
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
