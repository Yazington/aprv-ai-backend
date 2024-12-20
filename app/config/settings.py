import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

# Load .env.local if it exists, overriding any variables previously set
load_dotenv(dotenv_path=".env.local")


class Settings(BaseSettings):
    mongo_url: str | None = os.getenv("MONGO_URL")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    aprv_ai_api_key: str | None = os.getenv("APRV_AI_API_KEY")
    google_client_id: str | None = os.getenv("GOOGLE_CLIENT_ID")
    temp: str | None = os.getenv("TEMP")


settings = Settings()  # type: ignore
# print(settings)
