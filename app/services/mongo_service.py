import gridfs
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from odmantic import AIOEngine
from pymongo import MongoClient

from app.config.settings import settings


class MongoService:
    def __init__(self):
        # Async MongoDB client and GridFS
        self.async_client = AsyncIOMotorClient(settings.mongo_url)
        self.database_name = "aprv-ai"
        self.db_async = self.async_client[self.database_name]
        self.engine = AIOEngine(client=self.async_client, database=self.database_name)
        self.async_fs = AsyncIOMotorGridFSBucket(self.db_async)

        # Sync MongoDB client and GridFS
        self.sync_client = MongoClient(settings.mongo_url)
        self.db_sync = self.sync_client[self.database_name]
        self.sync_fs = gridfs.GridFS(self.db_sync)

async def get_mongo_service() -> MongoService:
    return MongoService()
