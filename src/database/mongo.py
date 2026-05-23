from __future__ import annotations

from typing import Any

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
            self.client = AsyncIOMotorClient(
                settings.mongodb_uri,
                serverSelectionTimeoutMS=settings.mongodb_server_selection_timeout_ms,
            )
            await self.client.admin.command("ping")
            self.database = self.client[settings.mongodb_database]
            self.collection = self.database[settings.mongodb_collection]
            await self.collection.create_index([("client_id", 1), ("timestamp", -1)])
            await self.collection.create_index([("browser_id", 1), ("timestamp", -1)])
            await self.collection.create_index([("timestamp", -1)])
            await self.collection.create_index([("prediction", 1)])
            await self.collection.create_index([("detected_type", 1)])
            self.available = True
            logger.info("Connected to MongoDB database '%s'.", settings.mongodb_database)
        except Exception as exc:  # pragma: no cover - depends on local infra.
            logger.warning("MongoDB unavailable; persistence is disabled: %s", exc)
            self.available = False

    async def close(self) -> None:
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed.")


mongo = MongoDatabase()
