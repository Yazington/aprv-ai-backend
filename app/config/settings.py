import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")

    class Config:
        env_file = ".env"


settings = Settings()  # type: ignore
