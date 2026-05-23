from __future__ import annotations

from fastapi import APIRouter

from src.config import settings
from src.database.mongo import mongo
from src.schemas.spam import HealthResponse
from src.services.prediction_service import prediction_service

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        environment=settings.environment,
        database="connected" if mongo.available else "unavailable",
        models=prediction_service.models_status(),
    )
