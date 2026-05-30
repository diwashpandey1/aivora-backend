from __future__ import annotations

import gc
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import settings
from src.database.mongo import mongo
from src.routes import analyze, health, history, stats, reset_memory
from src.services.prediction_service import prediction_service
from src.utils.logger import configure_logging, get_logger
from src.utils.memory import memory_monitor

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management with memory optimization.
    
    Startup:
    - Logs baseline memory usage
    - Warms up ML models (loads once, never reloads in requests)
    - Connects to MongoDB
    
    Shutdown:
    - Performs final garbage collection
    - Closes database connections
    """
    logger.info("=" * 60)
    logger.info("Application starting - initializing models and services")
    
    # Log memory usage after models are loaded
    # This establishes baseline for detecting leaks during runtime
    memory_monitor.log_startup_memory()
    
    # Load models once during startup (not per-request)
    # All models are cached in PredictionService._bundles dict
    prediction_service.warmup()
    
    # Log memory after model loading to understand static memory footprint
    memory_monitor.log_after_prediction(client_id="startup")
    
    # Connect to database
    await mongo.connect()
    
    logger.info("Application ready. Models loaded and database connected.")
    logger.info("=" * 60)
    
    yield
    
    # Shutdown: perform final cleanup
    logger.info("Application shutting down - closing connections")
    await mongo.close()
    
    # Final garbage collection to ensure clean shutdown
    # Helps prevent port conflicts on rapid restart scenarios
    gc.collect()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=settings.api_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers
app.include_router(health.router)
app.include_router(analyze.router)
app.include_router(history.router)
app.include_router(stats.router)
app.include_router(reset_memory.router)  # NEW: Memory management endpoints


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler with memory diagnostics logging.
    
    Logs all unhandled exceptions with current memory state.
    Helps identify if OOM conditions contributed to the error.
    """
    logger.exception("Unhandled request error on %s %s", request.method, request.url.path)
    
    # Log memory state when exception occurs (important for debugging OOM crashes)
    memory_monitor.log_exception_memory(exc)
    
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

