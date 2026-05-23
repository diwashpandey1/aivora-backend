from __future__ import annotations

import asyncio
from typing import Any

import certifi

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MongoDatabase:
    def __init__(self) -> None:
        self.client: Any | None = None
        self.database: Any | None = None
        self.collection: Any | None = None
        self.available = False

    async def connect(self) -> None:
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
        except ImportError:
            logger.warning("motor is not installed; MongoDB persistence is disabled.")
            return

        try:
            # Log connection details (without password)
            uri_display = settings.mongodb_uri.split("@")[-1] if "@" in settings.mongodb_uri else settings.mongodb_uri
            logger.info("Attempting to connect to MongoDB Atlas: %s", uri_display)

            # Build MongoDB client with proper TLS/SSL configuration
            client_options = {
                "serverSelectionTimeoutMS": settings.mongodb_server_selection_timeout_ms,
                "connectTimeoutMS": settings.mongodb_connect_timeout_ms,
                "socketTimeoutMS": settings.mongodb_socket_timeout_ms,
                "retryWrites": True,
                "w": "majority",
            }

            # For MongoDB Atlas (mongodb+srv:// URIs), enable TLS with certifi CA bundle
            if "mongodb+srv://" in settings.mongodb_uri:
                client_options["tlsCAFile"] = certifi.where()
                client_options["tls"] = True
                logger.debug("TLS/SSL enabled for MongoDB Atlas connection with certifi CA bundle")

            self.client = AsyncIOMotorClient(settings.mongodb_uri, **client_options)

            # Verify connection with ping
            await asyncio.wait_for(
                self.client.admin.command("ping"),
                timeout=settings.mongodb_server_selection_timeout_ms / 1000,
            )

            self.database = self.client[settings.mongodb_database]
            self.collection = self.database[settings.mongodb_collection]

            # Create indices for better query performance
            await self.collection.create_index([("client_id", 1), ("timestamp", -1)])
            await self.collection.create_index([("browser_id", 1), ("timestamp", -1)])
            await self.collection.create_index([("timestamp", -1)])
            await self.collection.create_index([("prediction", 1)])
            await self.collection.create_index([("detected_type", 1)])

            self.available = True
            logger.info("✓ Successfully connected to MongoDB database '%s'", settings.mongodb_database)

        except asyncio.TimeoutError:
            logger.error(
                "MongoDB connection timeout after %dms. Check network connectivity and MongoDB Atlas status.",
                settings.mongodb_server_selection_timeout_ms,
            )
            self.available = False
        except Exception as exc:
            logger.warning(
                "MongoDB connection failed; persistence is disabled. Error: %s | Type: %s",
                str(exc),
                type(exc).__name__,
            )
            self.available = False

    async def close(self) -> None:
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed.")


mongo = MongoDatabase()
