"""Memory management endpoint for Render free-tier deployments.

Provides diagnostic and memory reset functionality. Use this endpoint to:
- Trigger garbage collection
- Check current memory usage
- Identify potential memory leaks

POST /reset-memory - Trigger GC and get memory diagnostics
GET /memory-status - Get current memory state without GC
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from src.utils.memory import memory_monitor

router = APIRouter(tags=["memory-management"])


class MemoryStatus(BaseModel):
    """Current memory state and diagnostic info."""
    
    status: str
    gc_collected: int  # Number of objects freed by last gc.collect()
    current_memory: dict[str, float | int]  # RSS, VMS, percent
    gc_object_count: int  # Total unreferenced objects in gc tracking
    delta_from_startup_mb: float | None = None  # Memory change since startup


class MemoryResetResponse(BaseModel):
    """Response from memory reset operation."""
    
    status: str
    message: str
    memory_stats: MemoryStatus


@router.post("/reset-memory", response_model=MemoryResetResponse)
async def reset_memory() -> MemoryResetResponse:
    """Force garbage collection and return memory diagnostics.
    
    **Purpose**: Emergency memory recovery for Render free-tier environments.
    
    This endpoint:
    1. Forces Python garbage collection (gc.collect())
    2. Frees all unreferenced objects
    3. Returns current memory usage and diagnostics
    
    **Use cases**:
    - Manual memory recovery during high load
    - Periodic cleanup (via cron or monitoring service)
    - Debugging OOM issues
    
    **Response includes**:
    - gc_collected: Number of objects freed
    - current_memory: RSS (physical RAM), VMS (virtual), system percent
    - delta_from_startup_mb: Memory used since app start
    - gc_object_count: Total objects tracked by garbage collector
    """
    report = memory_monitor.cleanup_and_report()
    
    return MemoryResetResponse(
        status="success",
        message="Garbage collection completed. Check memory_stats for details.",
        memory_stats=MemoryStatus(
            status="ok",
            gc_collected=report["gc_collected"],
            current_memory=report["current_memory"],
            gc_object_count=report["gc_object_count"],
            delta_from_startup_mb=report.get("delta_from_startup_mb"),
        ),
    )


@router.get("/memory-status", response_model=MemoryStatus)
async def get_memory_status() -> MemoryStatus:
    """Get current memory status without triggering garbage collection.
    
    **Purpose**: Non-invasive memory monitoring for health checks and observability.
    
    Does NOT trigger gc.collect(), so returns memory state as-is (may include
    unreferenced objects not yet collected).
    
    Use this endpoint for:
    - Monitoring dashboards
    - Health check systems
    - Render alerts and auto-scaling
    
    Compare with /reset-memory to see potential GC savings.
    """
    snapshot = memory_monitor.get_snapshot()
    startup = memory_monitor._startup_snapshot
    delta = startup.rss_mb - snapshot.rss_mb if startup else None
    
    return MemoryStatus(
        status="ok",
        gc_collected=0,  # No collection performed
        current_memory={
            "rss_mb": snapshot.rss_mb,
            "vms_mb": snapshot.vms_mb,
            "percent_of_system": snapshot.percent,
        },
        gc_object_count=0,  # Not collected in this endpoint
        delta_from_startup_mb=delta,
    )

