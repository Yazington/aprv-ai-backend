# app/services/mongo_service.py
from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorClient
from odmantic import AIOEngine
from pymongo.database import Database


class MongoService:
    def __init__(self):
        self.client = AsyncIOMotorClient("mongodb://root:example@localhost:27017/")
        self.database_name = "aprv-ai"
        self.db: Database = self.client[self.database_name]
        self.engine = AIOEngine(client=self.client, database=self.database_name)


def get_mongo_service() -> MongoService:
    return MongoService()


mongo_service: MongoService = Depends(get_mongo_service)
