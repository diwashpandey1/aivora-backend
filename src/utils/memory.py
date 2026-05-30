"""Memory monitoring and management utilities for Render free-tier deployment.

Tracks RAM usage, manages garbage collection, and provides diagnostics for
memory-constrained environments. Designed to prevent OOM crashes on free-tier
hosting with limited memory (512MB).
"""
from __future__ import annotations

import gc
import os
from dataclasses import dataclass
from typing import Any

import psutil

from src.utils.logger import get_logger


logger = get_logger(__name__)


@dataclass
class MemorySnapshot:
    """Records memory state at a point in time."""
    
    rss_mb: float  # Resident Set Size (actual physical memory)
    vms_mb: float  # Virtual Memory Size
    percent: float  # Percentage of system memory used
    
    def __str__(self) -> str:
        return f"RSS: {self.rss_mb:.2f} MB | VMS: {self.vms_mb:.2f} MB | {self.percent:.1f}%"


class MemoryMonitor:
    """Monitors and manages memory usage across the application lifecycle."""
    
    def __init__(self) -> None:
        self.process = psutil.Process(os.getpid())
        self._startup_snapshot: MemorySnapshot | None = None
    
    def get_snapshot(self) -> MemorySnapshot:
        """Capture current memory usage."""
        try:
            mem_info = self.process.memory_info()
            rss_mb = mem_info.rss / 1024 / 1024
            vms_mb = mem_info.vms / 1024 / 1024
            percent = psutil.Process().memory_percent()
            return MemorySnapshot(rss_mb=rss_mb, vms_mb=vms_mb, percent=percent)
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.warning("Failed to capture memory snapshot: %s", e)
            return MemorySnapshot(rss_mb=0.0, vms_mb=0.0, percent=0.0)
    
    def log_startup_memory(self) -> MemorySnapshot:
        """Log memory usage after application startup. Call from lifespan startup."""
        self._startup_snapshot = self.get_snapshot()
        logger.info(
            "Startup Memory Usage: %s | Garbage objects: %d",
            self._startup_snapshot,
            len(gc.get_objects())
        )
        return self._startup_snapshot
    
    def log_before_prediction(self, client_id: str | None = None) -> MemorySnapshot:
        """Log memory before inference. Helps track allocation growth per request."""
        snapshot = self.get_snapshot()
        client_info = f" [client: {client_id}]" if client_id else ""
        logger.info("Memory Before Prediction%s: %s", client_info, snapshot)
        return snapshot
    
    def log_after_prediction(
        self,
        client_id: str | None = None,
        before_snapshot: MemorySnapshot | None = None,
    ) -> MemorySnapshot:
        """Log memory after inference and perform cleanup."""
        # Explicit garbage collection to free temporary objects created during inference
        # These include cleaned text, feature vectors, and intermediate numpy arrays
        gc.collect()
        
        snapshot = self.get_snapshot()
        client_info = f" [client: {client_id}]" if client_id else ""
        
        if before_snapshot:
            delta_mb = snapshot.rss_mb - before_snapshot.rss_mb
            delta_str = f"+{delta_mb:.2f}" if delta_mb > 0 else f"{delta_mb:.2f}"
            logger.info(
                "Memory After Prediction%s: %s | Delta: %s MB",
                client_info,
                snapshot,
                delta_str
            )
        else:
            logger.info("Memory After Prediction%s: %s", client_info, snapshot)
        
        return snapshot
    
    def log_exception_memory(self, exception: Exception) -> MemorySnapshot:
        """Log memory state when exception occurs. Critical for debugging OOM crashes."""
        snapshot = self.get_snapshot()
        logger.error(
            "Exception occurred with memory state: %s | Exception: %s | GC objects: %d",
            snapshot,
            type(exception).__name__,
            len(gc.get_objects())
        )
        return snapshot
    
    def cleanup_and_report(self) -> dict[str, Any]:
        """Perform cleanup and return memory diagnostics. Used by reset-memory endpoint."""
        # Force garbage collection to free all unreferenced objects
        collected = gc.collect()
        
        # Get updated snapshot after cleanup
        snapshot = self.get_snapshot()
        
        # Calculate memory saved from startup (if available)
        delta_from_startup = None
        if self._startup_snapshot:
            delta_from_startup = self._startup_snapshot.rss_mb - snapshot.rss_mb
        
        report = {
            "gc_collected": collected,  # Number of objects collected by gc
            "current_memory": {
                "rss_mb": snapshot.rss_mb,
                "vms_mb": snapshot.vms_mb,
                "percent_of_system": snapshot.percent,
            },
            "gc_object_count": len(gc.get_objects()),
        }
        
        if delta_from_startup is not None:
            report["delta_from_startup_mb"] = round(delta_from_startup, 2)
        
        logger.info("Memory cleanup completed: collected %d objects", collected)
        return report


# Global instance
memory_monitor = MemoryMonitor()