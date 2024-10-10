import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    aprv_ai_api_key: str | None = os.getenv("APRV_AI_API_KEY")
    google_client_id: str | None = os.getenv("GOOGLE_CLIENT_ID")

    class Config:
        env_file = ".env"


settings = Settings()  # type: ignore
