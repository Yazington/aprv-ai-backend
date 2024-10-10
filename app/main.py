import logging

from api import auth, chat, conversation, upload
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from middlewares.token_validation_middleware import TokenValidationMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = FastAPI(
    title="APRV AI Backend",
    description="Backend for APRV AI Chat Application",
    version="1.0.0",
)

# Configure CORS
origins = [
    "http://localhost",
    "http://localhost:3000",  # Adjust based on your frontend's address
    # Add other origins if necessary
]


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
