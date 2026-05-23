from __future__ import annotations

from fastapi import APIRouter

from src.schemas.spam import StatsResponse
from src.services.history_service import history_service

router = APIRouter(tags=["analytics"])


@router.get("/stats", response_model=StatsResponse)
async def get_stats() -> StatsResponse:
    return StatsResponse(**await history_service.get_stats())
