import pymongo
from gridfs import GridFS
from motor.motor_asyncio import AsyncIOMotorClient
from odmantic import AIOEngine

from app.config.settings import settings


class MongoService:
    """Service class for handling MongoDB connections and operations.

    This class provides both asynchronous and synchronous MongoDB clients to support
    different types of database operations. It uses AsyncIOMotorClient for async operations
    and pymongo.MongoClient for synchronous operations like GridFS file storage.
    """

    def __init__(self):
        """Initialize MongoDB connections and services.

        Creates both asynchronous and synchronous MongoDB clients using the connection URL
        from settings. Sets up the database and ODM (Object Document Mapper) engine for
        async operations, and GridFS for file storage.
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
        self.engine = AIOEngine(client=self.client, database=self.database_name)

        # Use pymongo.MongoClient for GridFS (synchronous operations) with timeout settings
        self.client_sync = pymongo.MongoClient(
            settings.mongo_url, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000, socketTimeoutMS=5000
        )
        self.db_sync = self.client_sync[self.database_name]
        self.fs = GridFS(self.db_sync)


def get_mongo_service() -> MongoService:
    """Factory function to create and return a MongoService instance.

    Returns:
        MongoService: A new instance of the MongoService class
    """
    return MongoService()
