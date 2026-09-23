import os
import sys
import pymongo

from src.exception import MyException
from src.logger import logging
from src.constants import DATABASE_NAME, MONGODB_URL_KEY


class MongoDBClient:
    """
    MongoDBClient is responsible for establishing a connection
    to the MongoDB database.
    """

    client = None

    def __init__(self, database_name: str = DATABASE_NAME) -> None:
        """
        Initialize a MongoDB connection.

        Parameters
        ----------
        database_name : str
            Name of the MongoDB database.
        """

        try:
            # Create a MongoDB client only once
            if MongoDBClient.client is None:

                mongo_db_url = os.getenv(MONGODB_URL_KEY)

                if not mongo_db_url:
                    raise Exception(
                        f"Environment variable '{MONGODB_URL_KEY}' is not set."
                    )

                # Create MongoDB client
                MongoDBClient.client = pymongo.MongoClient(
                    mongo_db_url,
                    serverSelectionTimeoutMS=30000,
                    connectTimeoutMS=30000
                )

                # Force a connection test
                MongoDBClient.client.admin.command("ping")

            # Use the shared MongoDB client
            self.client = MongoDBClient.client

            # Select database
            self.database = self.client[database_name]

            self.database_name = database_name

            logging.info("MongoDB connection successful.")

        except Exception as e:
            raise MyException(e, sys)