from __future__ import annotations

import gc

from fastapi import APIRouter, HTTPException, status

from src.schemas.spam import AnalyzeRequest, AnalyzeResponse
from src.services.history_service import history_service
from src.services.prediction_service import ModelNotReadyError, prediction_service
from src.utils.memory import memory_monitor

router = APIRouter(tags=["analysis"])


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_payload(payload: AnalyzeRequest) -> AnalyzeResponse:
    try:
        # Memory monitoring is also done inside prediction_service.analyze()
        # This route-level call ensures we have comprehensive logging if needed
        result = prediction_service.analyze(payload.message, client_id=payload.client_id)
    except ModelNotReadyError as exc:
        # Log memory state when model initialization fails
        memory_monitor.log_exception_memory(exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        # Log memory state for any unexpected errors
        # This helps diagnose if OOM conditions contributed to the failure
        memory_monitor.log_exception_memory(exc)
        raise

    await history_service.save_scan(
        client_id=payload.client_id,
        message=payload.message,
        result=result,
    )
    return AnalyzeResponse(**result)
