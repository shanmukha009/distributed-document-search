"""
Distributed Document Search Service — Main Application.

A FastAPI application implementing enterprise-grade multi-tenant document search
with sub-second response times using Elasticsearch, Redis, and PostgreSQL.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from src.api import documents, search, health
from src.services.elasticsearch_service import es_service
from src.services.redis_service import redis_service
from src.services.postgres_service import pg_service
from src.config.settings import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Startup: Connect to all services.
    Shutdown: Gracefully disconnect.
    """
    logger.info("Starting Distributed Document Search Service...")
    
    # Connect to services
    await es_service.connect()
    await redis_service.connect()
    await pg_service.connect()
    
    logger.info("All services connected. Ready to serve traffic.")
    
    yield
    
    # Cleanup
    logger.info("Shutting down...")
    await es_service.disconnect()
    await redis_service.disconnect()
    await pg_service.disconnect()
    logger.info("Shutdown complete.")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    Distributed Document Search Service with enterprise-grade multi-tenancy.
    
    ## Features
    * Full-text search with relevance ranking (Elasticsearch)
    * Multi-tenant with strict data isolation
    * Sub-second response times with Redis caching
    * Rate limiting per tenant
    * Health checks with dependency status
    """,
    lifespan=lifespan
)


# Register routers
app.include_router(documents.router)
app.include_router(search.router)
app.include_router(health.router)


@app.get("/", tags=["root"])
async def root():
    """Root endpoint with API information."""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health"
    }


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """Return validation errors in our standard format."""
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": exc.errors()
            }
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)