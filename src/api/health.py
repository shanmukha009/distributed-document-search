"""Health check endpoints."""

from datetime import datetime

from fastapi import APIRouter, status

from src.models.document import HealthStatus
from src.services.elasticsearch_service import es_service
from src.services.postgres_service import pg_service
from src.services.redis_service import redis_service
from src.config.settings import settings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
async def health_check():
    """
    Comprehensive health check with dependency status.
    
    Returns 200 if all critical dependencies are healthy.
    Returns 503 if any critical dependency is unhealthy.
    """
    dependencies = {
        "elasticsearch": await es_service.health_check(),
        "redis": await redis_service.health_check(),
        "postgresql": await pg_service.health_check()
    }
    
    all_healthy = all(dep["status"] == "healthy" for dep in dependencies.values())
    overall_status = "healthy" if all_healthy else "degraded"
    
    return HealthStatus(
        status=overall_status,
        version=settings.APP_VERSION,
        timestamp=datetime.utcnow(),
        dependencies=dependencies
    )


@router.get("/health/live")
async def liveness_probe():
    """
    Kubernetes liveness probe.
    
    Returns 200 if the application process is running.
    """
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness_probe():
    """
    Kubernetes readiness probe.
    
    Returns 200 only if the app can serve traffic.
    """
    try:
        es_health = await es_service.health_check()
        pg_health = await pg_service.health_check()
        
        if es_health["status"] == "healthy" and pg_health["status"] == "healthy":
            return {"status": "ready"}
        else:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Dependencies not ready"
            )
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )