import pymongo
from config.settings import settings
from fastapi import Depends
from gridfs import GridFS
from motor.motor_asyncio import AsyncIOMotorClient
from odmantic import AIOEngine


class MongoService:
    def __init__(self):
        # Use AsyncIOMotorClient for asynchronous operations
        self.client = AsyncIOMotorClient(settings.mongo_url)
        self.database_name = "aprv-ai"
        self.db_async = self.client[self.database_name]
        self.engine = AIOEngine(client=self.client, database=self.database_name)

        # Use pymongo.MongoClient for GridFS
        self.client_sync = pymongo.MongoClient(settings.mongo_url)
        self.db_sync = self.client_sync[self.database_name]
        self.fs = GridFS(self.db_sync)


def get_mongo_service() -> MongoService:
    return MongoService()


mongo_service: MongoService = Depends(get_mongo_service)
