from motor.motor_asyncio import AsyncIOMotorClient
from odmantic import AIOEngine
from app.config.logging_config import logger
from app.config.settings import settings


class MongoService:
    """Service class for handling MongoDB connections and operations using odmantic.

    This class provides MongoDB operations through odmantic's AIOEngine for all database
    operations. It simplifies the codebase by using a single ODM library.
    """

    def __init__(self):
        """Initialize MongoDB connection using odmantic's AIOEngine.

        Creates the database engine using the connection URL from settings.
        """
        try:
            logger.info("Initializing MongoDB connection...")
            self.database_name = "aprv-ai"
            logger.info(f"Using database: {self.database_name}")
            
            if not settings.mongo_url:
                logger.error("MongoDB URL is not set in environment variables")
                raise ValueError("MongoDB URL is not configured")
            
            # Log a sanitized version of the MongoDB URL (hiding credentials)
            mongo_url = settings.mongo_url
            if '@' in mongo_url:
                # Only show the part after @ to avoid logging credentials
                safe_url = '***@' + mongo_url.split('@')[1]
            else:
                safe_url = '***'
            logger.info(f"Connecting to MongoDB at: {safe_url}")
            
            logger.info("Creating MongoDB client...")
            self.client = AsyncIOMotorClient(
                settings.mongo_url,
                serverSelectionTimeoutMS=5000,  # 5 second timeout for server selection
                connectTimeoutMS=5000,  # 5 second timeout for connection
                socketTimeoutMS=5000,  # 5 second timeout for socket operations
            )
            logger.info("Creating AIOEngine...")
            self.engine = AIOEngine(client=self.client, database=self.database_name)
            logger.info("MongoDB initialization completed successfully")
        except Exception as e:
            logger.error(f"Error initializing MongoDB connection: {str(e)}")
            logger.error(f"Original exception type: {type(e).__name__}")
            raise

    async def initialize(self):
        """Initialize the database connection.
        
        Verifies the connection is working by attempting to connect to the server.
        """
        try:
            logger.info("Testing MongoDB connection...")
            # Test the connection by running a simple command
            await self.client.admin.command('ping')
            logger.info("MongoDB connection test successful")
            
            # List available databases to verify permissions
            databases = await self.client.list_database_names()
            logger.info(f"Available databases: {', '.join(databases)}")
            
            # Verify we can access our specific database
            if self.database_name in databases:
                logger.info(f"Successfully found database: {self.database_name}")
            else:
                logger.warning(f"Database '{self.database_name}' not found. It will be created on first use.")
                
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            logger.error(f"Original exception type: {type(e).__name__}")
            logger.error("Please verify MongoDB URL and credentials are correctly configured")
            raise


async def get_mongo_service() -> MongoService:
    """Factory function to create and return a MongoService instance.

    Returns:
        MongoService: An instance of the MongoService class
    """
    service = MongoService()
    await service.initialize()
    return service
