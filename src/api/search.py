"""Search endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Header, Query, status

from src.models.document import SearchResponse, SearchResult
from src.services.elasticsearch_service import es_service
from src.services.redis_service import redis_service
from src.config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["search"])


def _validate_tenant(tenant_id: str | None) -> str:
    """Validate that tenant ID header was provided."""
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "MISSING_TENANT_ID",
                    "message": f"{settings.TENANT_HEADER} header is required"
                }
            }
        )
    return tenant_id


@router.get("/search", response_model=SearchResponse)
async def search_documents(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID")
):
    """
    Full-text search across documents.
    
    Implements cache-aside pattern:
    1. Check Redis cache
    2. On miss, query Elasticsearch
    3. Store results in cache with TTL
    """
    tenant_id = _validate_tenant(x_tenant_id)
    
    # Rate limiting
    allowed, remaining = await redis_service.check_rate_limit(
        tenant_id,
        limit_per_minute=settings.RATE_LIMIT_FREE
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Rate limit exceeded. Try again in 60 seconds.",
                    "details": {"remaining": remaining}
                }
            }
        )
    
    # 1. Check cache first
    cached = await redis_service.get_cached_search(tenant_id, q, offset, limit)
    if cached:
        logger.info(f"Cache HIT for tenant {tenant_id}, query '{q}'")
        return SearchResponse(
            total=cached["total"],
            limit=limit,
            offset=offset,
            took_ms=cached.get("took_ms", 0),
            cached=True,
            results=[SearchResult(**r) for r in cached["results"]]
        )
    
    # 2. Cache miss — query Elasticsearch
    logger.info(f"Cache MISS for tenant {tenant_id}, query '{q}'")
    es_result = await es_service.search(
        tenant_id=tenant_id,
        query=q,
        limit=limit,
        offset=offset
    )
    
    # 3. Cache the result
    await redis_service.set_cached_search(
        tenant_id=tenant_id,
        query=q,
        offset=offset,
        limit=limit,
        results=es_result
    )
    
    return SearchResponse(
        total=es_result["total"],
        limit=limit,
        offset=offset,
        took_ms=es_result.get("took_ms", 0),
        cached=False,
        results=[SearchResult(**r) for r in es_result["results"]]
    )