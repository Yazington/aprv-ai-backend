from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth, chat, conversation, upload
from app.middlewares.token_validation_middleware import TokenValidationMiddleware

# Initialize FastAPI application with metadata
app = FastAPI(
    title="APRV AI Backend",
    description="Backend for APRV AI Chat Application",
    version="1.0.0",
)


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

# Generate and save OpenAPI schema to file
with open("openapi.json", "w") as f:
    import json
    openapi_schema = app.openapi()
    json.dump(openapi_schema, f, indent=2)
