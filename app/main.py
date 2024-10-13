import logging

from api import auth, chat, conversation, upload
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from middlewares.token_validation_middleware import TokenValidationMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = FastAPI(
    title="APRV AI Backend",
    description="Backend for APRV AI Chat Application",
    version="1.0.0",
)

# # Configure CORS
# origins = [
#     "http://localhost",
#     "http://localhost:3000",  # Adjust based on your frontend's address
#     # Add other origins if necessary
# ]


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers={
            "Access-Control-Allow-Origin": "*",  # Replace with your allowed origins
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Replace with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers, including Authorization
)

app.add_middleware(TokenValidationMiddleware)

app.include_router(chat.router)
app.include_router(upload.router)
app.include_router(auth.router)
app.include_router(conversation.router)
