import datetime
from typing import Annotated, Optional, Union

from fastapi import Depends
from odmantic.exceptions import DocumentNotFoundError

from app.models.users import GoogleAuthInfo, User
from app.services.mongo_service import MongoService, get_mongo_service
from app.config.logging_config import logger


class UserService:
    def __init__(self, mongo_service: MongoService):
        """Initialize UserService with a MongoService instance.

        Args:
            mongo_service (MongoService): The MongoDB service instance used for database operations.
        """
        self.mongo_service = mongo_service

    async def get_user_by_email(self, email: str) -> Union[User, None]:
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
            user = await self.mongo_service.engine.find_one(User, User.email == email)
            return user
        except Exception as e:
            logger.error(f"Database error during fetching user by email: {str(e)}")
            logger.error(f"Original exception type: {type(e).__name__}")
            return None

    async def create_user(self, email: str, google_auth_info: GoogleAuthInfo) -> User:
        """Create a new user with Google authentication information.

        This method creates a new user object and saves it to the database using the provided email
        address and Google authentication details.

        Args:
            email (str): The email address of the new user.
            google_auth_info (GoogleAuthInfo): The Google authentication information for the user.

        Returns:
            User: The newly created user object.
        """
        if not google_auth_info.given_name:
            logger.warning("given_name is missing from Google auth info")
            given_name = email.split('@')[0]  # Use part of email as fallback
        else:
            given_name = google_auth_info.given_name

        if not google_auth_info.family_name:
            logger.warning("family_name is missing from Google auth info")
            family_name = ""  # Empty string as fallback
        else:
            family_name = google_auth_info.family_name
        
        if not google_auth_info.picture:
            logger.warning("picture is missing from Google auth info")
            picture = ""  # Empty string as fallback
        else:
            picture = google_auth_info.picture

        logger.info(f"family_name: {family_name}")
        new_user = User(
            email=email,
            given_name=given_name,
            family_name=family_name,
            picture=picture
        )
        logger.info(f"creating user db object: {new_user}")
        saved_user = await self.mongo_service.engine.save(new_user)
        return saved_user

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
            await self.mongo_service.engine.save(user)
        except DocumentNotFoundError:
            raise Exception("User not found during update")
        except Exception as e:
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
        try:
            existing_user = await self.get_user_by_email(email)
            print(existing_user)
            if existing_user:
                # Update existing user's info
                existing_user.given_name = google_auth_info.given_name
                existing_user.family_name = google_auth_info.family_name
                existing_user.picture = google_auth_info.picture
                await self.update_user(existing_user)
                return existing_user
            else:
                logger.info(f"Creating new user with email: {email}")
                new_user = await self.create_user(email, google_auth_info)
                return new_user
        except Exception as e:
            logger.error(f"Error in get_or_create_user for email {email}: {str(e)}")
            logger.error(f"Original exception type: {type(e).__name__}")
            raise


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
