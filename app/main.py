import logging

from api import chat, upload
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# logger = logging.getLogger("my_logger")
# handler = logging.StreamHandler()
# formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
# handler.setFormatter(formatter)
# logger.addHandler(handler)

# # Set the logger level to ERROR or higher if you want to avoid debug/info logs
# logger.setLevel(logging.ERROR)

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
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods
    allow_headers=["*"],  # Allows all headers
)

app.include_router(chat.router)
app.include_router(upload.router)
