import datetime
from typing import Annotated

from fastapi import Depends
from odmantic import ObjectId
from pymongo.errors import PyMongoError

from app.models.users import GoogleAuthInfo, User
from app.services.mongo_service import MongoService, get_mongo_service


class UserService:
    def __init__(self, mongo_service: MongoService):
        self.mongo_service = mongo_service

    async def get_user_by_email(self, email: str) -> User:
        """Fetch a user by email."""
        try:
            return await self.mongo_service.engine.find_one(User, {"email": email})
        except PyMongoError as e:
            # Include the original error details
            raise Exception(f"Database error during fetching user by email: {str(e)}") from e

    async def create_user(self, email: str, google_auth_info: GoogleAuthInfo) -> User:
        """Create a new user."""
        try:
            # new_user_data = {"email": email, "google_auth": google_auth_info.dict()}
            new_user = User(id=ObjectId(), email=email, google_auth=google_auth_info)
            await self.mongo_service.engine.save(new_user)
            return new_user
        except PyMongoError as e:
            # Handle or log the error as needed
            raise Exception("Database error during creating user") from e

    async def update_user(self, user: User) -> None:
        """Update an existing user's information."""
        try:
            user.modified_at = datetime.datetime.utcnow()
            await self.mongo_service.engine.save(user)
        except PyMongoError as e:
            # Handle or log the error as needed
            raise Exception("Database error during updating user") from e

    async def get_or_create_user(self, email: str, google_auth_info: GoogleAuthInfo) -> User:
        """Fetch a user by email or create a new one if it doesn't exist."""
        existing_user = await self.get_user_by_email(email)
        if existing_user:
            existing_user.google_auth = google_auth_info
            await self.update_user(existing_user)
            return existing_user
        else:
            return await self.create_user(email, google_auth_info)


def get_user_service(mongo_service: Annotated[MongoService, Depends(get_mongo_service)]) -> UserService:
    return UserService(mongo_service=mongo_service)
