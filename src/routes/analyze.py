from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from src.schemas.spam import AnalyzeRequest, AnalyzeResponse
from src.services.history_service import history_service
from src.services.prediction_service import ModelNotReadyError, prediction_service

router = APIRouter(tags=["analysis"])


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_payload(payload: AnalyzeRequest) -> AnalyzeResponse:
    try:
        result = prediction_service.analyze(payload.message)
    except ModelNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    await history_service.save_scan(
        client_id=payload.client_id,
        message=payload.message,
        result=result,
    )
    return AnalyzeResponse(**result)
