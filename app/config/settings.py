import os

# Import necessary modules for loading environment variables and settings
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load environment variables from a .env file into the environment
load_dotenv()

# Load .env.local if it exists, overriding any variables previously set
load_dotenv(dotenv_path=".env.local")


# Define a Settings class that inherits from BaseSettings
class Settings(BaseSettings):
    # Define attributes for the settings, with default values from environment variables
    mongo_url: str = os.getenv("MONGO_URL", "")  # MongoDB connection URL
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")  # OpenAI API key
    aprv_ai_api_key: str = os.getenv("APRV_AI_API_KEY", "")  # APRV AI API key
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")  # Google client ID
    temp: str = os.getenv("TEMP", "")  # Temporary directory path

    # AWS credentials for Textract
    aws_access_key_id: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    aws_secret_access_key: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")  # Default to us-east-1

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )


# Instantiate the Settings class to load the settings
settings = Settings()  # type: ignore
# Uncomment the line below to print the settings for debugging purposes
# print(settings)
