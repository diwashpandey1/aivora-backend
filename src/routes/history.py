from __future__ import annotations

from fastapi import APIRouter, Query

from src.schemas.spam import DeleteHistoryResponse, HistoryResponse
from src.services.history_service import history_service

router = APIRouter(tags=["history"])


@router.get("/history/{client_id}", response_model=HistoryResponse)
async def get_history(
    client_id: str,
    limit: int = Query(default=100, ge=1, le=500),
) -> HistoryResponse:
    items = await history_service.get_history(client_id, limit=limit)
    return HistoryResponse(client_id=client_id, total=len(items), items=items)


@router.delete("/history/{client_id}", response_model=DeleteHistoryResponse)
async def delete_history(client_id: str) -> DeleteHistoryResponse:
    deleted_count = await history_service.delete_history(client_id)
    return DeleteHistoryResponse(client_id=client_id, deleted_count=deleted_count)
