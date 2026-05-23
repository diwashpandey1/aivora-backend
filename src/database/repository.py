from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from src.database.mongo import mongo


def _serialize(document: dict[str, Any]) -> dict[str, Any]:
    doc = dict(document)
    doc["id"] = str(doc.pop("_id", ""))
    doc["client_id"] = doc.get("client_id") or doc.get("browser_id", "")
    doc["message"] = doc.get("original_message") or doc.get("message", "")
    doc["safe_probability"] = doc.get(
        "safe_probability",
        round(1 - float(doc.get("spam_probability", 0.0)), 4),
    )
    doc["keywords_detected"] = doc.get("keywords_detected") or doc.get(
        "detected_keywords",
        [],
    )
    return doc


class ScanRepository:
    async def create_scan(self, payload: dict[str, Any]) -> str | None:
        if not mongo.available or mongo.collection is None:
            return None

        payload = dict(payload)
        payload.setdefault("timestamp", datetime.now(timezone.utc))
        result = await mongo.collection.insert_one(payload)
        return str(result.inserted_id)

    async def get_history(self, client_id: str, limit: int = 100) -> list[dict[str, Any]]:
        if not mongo.available or mongo.collection is None:
            return []

        cursor = (
            mongo.collection.find(
                {"$or": [{"client_id": client_id}, {"browser_id": client_id}]}
            )
            .sort("timestamp", -1)
            .limit(limit)
        )
        return [_serialize(document) async for document in cursor]

    async def delete_history(self, client_id: str) -> int:
        if not mongo.available or mongo.collection is None:
            return 0

        result = await mongo.collection.delete_many(
            {"$or": [{"client_id": client_id}, {"browser_id": client_id}]}
        )
        return int(result.deleted_count)

    async def get_stats(self) -> dict[str, Any]:
        if not mongo.available or mongo.collection is None:
            return {
                "total_scans": 0,
                "spam_percentage": 0.0,
                "safe_percentage": 0.0,
                "type_counts": {"sms": 0, "email": 0},
                "prediction_counts": {"spam": 0, "safe": 0},
                "keyword_frequency": [],
                "prediction_timeline": [],
                "pie_chart_values": [
                    {"label": "spam", "value": 0},
                    {"label": "safe", "value": 0},
                ],
            }

        cursor = mongo.collection.find(
            {},
            {
                "prediction": 1,
                "detected_type": 1,
                "keywords_detected": 1,
                "detected_keywords": 1,
                "timestamp": 1,
            },
        )

        total = 0
        prediction_counts = Counter({"spam": 0, "safe": 0})
        type_counts = Counter({"sms": 0, "email": 0})
        keywords = Counter()
        timeline = defaultdict(lambda: Counter({"spam": 0, "safe": 0}))

        async for doc in cursor:
            total += 1
            prediction = doc.get("prediction", "safe")
            detected_type = doc.get("detected_type", "sms")
            prediction_counts[prediction] += 1
            type_counts[detected_type] += 1
            keywords.update(doc.get("keywords_detected") or doc.get("detected_keywords", []))

            timestamp = doc.get("timestamp")
            if isinstance(timestamp, datetime):
                bucket = timestamp.date().isoformat()
                timeline[bucket][prediction] += 1

        spam_count = prediction_counts["spam"]
        safe_count = prediction_counts["safe"]
        spam_percentage = round((spam_count / total) * 100, 2) if total else 0.0
        safe_percentage = round((safe_count / total) * 100, 2) if total else 0.0

        return {
            "total_scans": total,
            "spam_percentage": spam_percentage,
            "safe_percentage": safe_percentage,
            "type_counts": dict(type_counts),
            "prediction_counts": dict(prediction_counts),
            "keyword_frequency": [
                {"keyword": keyword, "count": count}
                for keyword, count in keywords.most_common(20)
            ],
            "prediction_timeline": [
                {
                    "date": date,
                    "spam": counts["spam"],
                    "safe": counts["safe"],
                    "total": counts["spam"] + counts["safe"],
                }
                for date, counts in sorted(timeline.items())
            ],
            "pie_chart_values": [
                {"label": "spam", "value": spam_count},
                {"label": "safe", "value": safe_count},
            ],
        }


scan_repository = ScanRepository()
