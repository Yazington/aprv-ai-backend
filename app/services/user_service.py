import datetime
from typing import Annotated, Optional

from fastapi import Depends
from odmantic import ObjectId
from pymongo.errors import PyMongoError

from app.models.users import GoogleAuthInfo, User
from app.services.mongo_service import MongoService, get_mongo_service


# Main service class for handling user-related operations
# Uses MongoDB through MongoService for persistence
class UserService:
    def __init__(self, mongo_service: MongoService):
        """Initialize UserService with a MongoService instance.

        Args:
            mongo_service (MongoService): The MongoDB service instance used for database operations.
        """
        self.mongo_service = mongo_service

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Fetch a user by email.

        This method queries the database to find a user with the specified email address.

        Args:
            email (str): The email address of the user to retrieve.

        Returns:
            User or None: The user object if found, otherwise None.

        Raises:
            Exception: If there's a database error during the operation.
        """
        try:
            # Query MongoDB using the email field as the search criteria
            return await self.mongo_service.engine.find_one(User, User.email == email)
        except PyMongoError as e:
            # Convert MongoDB-specific error to a generic exception
            raise Exception("Database error during fetching user by email") from e

    async def create_user(self, email: str, google_auth_info: GoogleAuthInfo) -> User:
        """Create a new user with Google authentication information.

        This method creates a new user object and saves it to the database using the provided email
        address and Google authentication details.

        Args:
            email (str): The email address of the new user.
            google_auth_info (GoogleAuthInfo): The Google authentication information for the user.

        Returns:
            User: The newly created user object.

        Raises:
            Exception: If there's a database error during creation.
        """
        try:
            # Create new User instance with generated ObjectId
            new_user = User(id=ObjectId(), email=email, google_auth=google_auth_info)
            # Save the new user to MongoDB
            await self.mongo_service.engine.save(new_user)
            return new_user
        except PyMongoError as e:
            # Convert MongoDB-specific error to a generic exception
            raise Exception("Database error during creating user") from e

    async def update_user(self, user: User) -> None:
        """Update an existing user's information in the database.

        This method updates the provided user object in the database. It sets the modified_at timestamp
        to the current UTC time before saving the changes.

        Args:
            user (User): The user object to update.

        Raises:
            Exception: If there's a database error during update.
        """
        try:
            # Update the modified_at timestamp to current UTC time
            user.modified_at = datetime.datetime.utcnow()
            # Save the updated user to MongoDB
            await self.mongo_service.engine.save(user)
        except PyMongoError as e:
            # Convert MongoDB-specific error to a generic exception
            raise Exception("Database error during updating user") from e

    async def get_or_create_user(self, email: str, google_auth_info: GoogleAuthInfo) -> User:
        """Fetch a user by email or create a new one if it doesn't exist.

        This convenience method attempts to retrieve a user with the specified email address. If no
        such user exists, it creates a new user with the provided email and Google authentication
        information.

        Args:
            email (str): The email address to search for or create with.
            google_auth_info (GoogleAuthInfo): The Google authentication details for the user.

        Returns:
            User: Either the existing user or the newly created user.
        """
        # Try to find existing user
        existing_user = await self.get_user_by_email(email)
        if existing_user:
            # Update existing user's Google auth info
            existing_user.google_auth = google_auth_info
            await self.update_user(existing_user)
            return existing_user
        else:
            # Create new user if none exists
            return await self.create_user(email, google_auth_info)


def get_user_service(mongo_service: Annotated[MongoService, Depends(get_mongo_service)]) -> UserService:
    """Dependency injection factory for creating UserService instances.

    This function is used to create and provide UserService instances, which are dependent on the
    MongoService instance provided by the dependency injection framework.

    Args:
        mongo_service (MongoService): The MongoDB service instance used for database operations.

    Returns:
        UserService: A new UserService instance.
    """
    return UserService(mongo_service=mongo_service)
