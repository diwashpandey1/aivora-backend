from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.database.repository import scan_repository


class HistoryService:
    async def save_scan(
        self,
        client_id: str,
        message: str,
        result: dict[str, Any],
    ) -> str | None:
        return await scan_repository.create_scan(
            {
                "client_id": client_id,
                "original_message": message,
                "detected_type": result["detected_type"],
                "prediction": result["prediction"],
                "confidence": result["confidence"],
                "spam_probability": result["spam_probability"],
                "safe_probability": result["safe_probability"],
                "keywords_detected": result["keywords_detected"],
                "risk_level": result["risk_level"],
                "timestamp": datetime.now(timezone.utc),
            }
        )

    async def get_history(self, client_id: str, limit: int = 100) -> list[dict[str, Any]]:
        return await scan_repository.get_history(client_id, limit=limit)

    async def delete_history(self, client_id: str) -> int:
        return await scan_repository.delete_history(client_id)

    async def get_stats(self) -> dict[str, Any]:
        return await scan_repository.get_stats()


history_service = HistoryService()
