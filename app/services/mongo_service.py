import pymongo
from beanie import init_beanie
from gridfs import GridFS
from motor.motor_asyncio import AsyncIOMotorClient

from app.config.settings import settings
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.review import Review
from app.models.task import Task
from app.models.users import User


class MongoService:
    """Service class for handling MongoDB connections and operations.

    This class provides both asynchronous and synchronous MongoDB clients to support
    different types of database operations. It uses AsyncIOMotorClient for async operations
    and pymongo.MongoClient for synchronous operations like GridFS file storage.
    """

    def __init__(self):
        """Initialize MongoDB connections and services.

        Creates both asynchronous and synchronous MongoDB clients using the connection URL
        from settings. Sets up the database connections.
        """
        # Use AsyncIOMotorClient for asynchronous operations with timeout settings
        self.client = AsyncIOMotorClient(
            settings.mongo_url,
            serverSelectionTimeoutMS=5000,  # 5 second timeout for server selection
            connectTimeoutMS=5000,  # 5 second timeout for connection
            socketTimeoutMS=5000,  # 5 second timeout for socket operations
        )
        self.database_name = "aprv-ai"
        self.db_async = self.client[self.database_name]

        # Use pymongo.MongoClient for GridFS (synchronous operations) with timeout settings
        self.client_sync = pymongo.MongoClient(
            settings.mongo_url, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000, socketTimeoutMS=5000
        )
        self.db_sync = self.client_sync[self.database_name]
        self.fs = GridFS(self.db_sync)

    async def initialize(self):
        """Initialize Beanie with all document models.
        
        This needs to be called after instantiation to set up the ODM.
        """
        await init_beanie(
            database=self.db_async,
            document_models=[
                User,
                Conversation,
                Message,
                Review,
                Task
            ]
        )


async def get_mongo_service() -> MongoService:
    """Factory function to create and return an initialized MongoService instance.

    Returns:
        MongoService: An initialized instance of the MongoService class
    """
    service = MongoService()
    await service.initialize()
    return service
