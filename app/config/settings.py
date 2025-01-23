import os

from pydantic_settings import BaseSettings

# Load environment variables from a .env file into the environment
# load_dotenv()


# Define a Settings class that inherits from BaseSettings
class Settings(BaseSettings):
    # Define attributes for the settings, with default values from environment variables
    mongo_url: str | None = os.getenv("MONGO_URL")  # MongoDB connection URL
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")  # OpenAI API key
    aprv_ai_api_key: str | None = os.getenv("APRV_AI_API_KEY")  # APRV AI API key
    google_client_id: str | None = os.getenv("GOOGLE_CLIENT_ID")  # Google client ID
    pinecone_api_key: str | None = os.getenv("PINECONE_API_KEY")  # Pinecone API key
    temp: str | None = os.getenv("TEMP")  # Temporary directory path



# Instantiate the Settings class to load the settings
settings = Settings()  # type: ignore
# Uncomment the line below to print the settings for debugging purposes
# print(settings)
