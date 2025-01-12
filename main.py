from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from dotenv import load_dotenv
import os

# Load environment variables from .env.production
load_dotenv('.env.production')

from app.api import auth, chat, conversation, upload
from app.middlewares.token_validation_middleware import TokenValidationMiddleware
from app.services.mongo_service import MongoService, get_mongo_service
from app.config.logging_config import logger

# Initialize FastAPI application with metadata
app = FastAPI(
    title="APRV AI Backend",
    description="Backend for APRV AI Chat Application",
    version="1.0.0",
)

# Initialize MongoDB service
mongo_service = None

@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup"""
    try:
        logger.info("Initializing MongoDB and Beanie...")
        global mongo_service
        mongo_service = MongoService()
        await mongo_service.initialize()
        logger.info("MongoDB and Beanie initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize MongoDB: {str(e)}")
        raise

# Override the get_mongo_service dependency
async def get_mongo_service_override():
    if mongo_service is None:
        raise RuntimeError("MongoDB service not initialized")
    return mongo_service

# Replace the default dependency with our override
app.dependency_overrides[get_mongo_service] = get_mongo_service_override


# Custom exception handler for HTTP errors
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers={
            "Access-Control-Allow-Origin": "*",  # Allow all origins for error responses
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )


# Configure CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Local development
        "http://localhost:4173",  # Local preview
        "http://localhost:8081",  # Additional local port
        "https://app.aprv.ai",  # Production environment
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Add token validation middleware for authentication
app.add_middleware(TokenValidationMiddleware)

# Include all API routers
app.include_router(chat.router)  # Chat-related endpoints
app.include_router(upload.router)  # File upload endpoints
app.include_router(auth.router)  # Authentication endpoints
app.include_router(conversation.router)  # Conversation management endpoints

if __name__ == "__main__":
    config = uvicorn.Config("main:app", port=9000, log_level="info")
    server = uvicorn.Server(config)
    server.run()
