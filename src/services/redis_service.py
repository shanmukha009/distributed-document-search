"""Redis service for caching and rate limiting."""

import hashlib
import json
import logging
from typing import Optional

import redis.asyncio as redis

from src.config.settings import settings

logger = logging.getLogger(__name__)


class RedisService:
    """
    Handles all Redis operations for caching and rate limiting.
    
    Cache keys are always namespaced with tenant_id to prevent
    cross-tenant data leakage.
    """
    
    def __init__(self):
        self.client: Optional[redis.Redis] = None
    
    async def connect(self):
        """Initialize Redis connection."""
        self.client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        logger.info(f"Connected to Redis at {settings.REDIS_URL}")
    
    async def disconnect(self):
        """Close Redis connection."""
        if self.client:
            await self.client.close()
    
    def _build_search_key(self, tenant_id: str, query: str, offset: int, limit: int) -> str:
        """
        Build cache key for search results.
        
        Includes tenant_id for security, query hash for uniqueness.
        """
        query_hash = hashlib.sha256(
            f"{query.lower().strip()}:{offset}:{limit}".encode()
        ).hexdigest()[:16]
        return f"v1:search:{tenant_id}:{query_hash}"
    
    def _build_document_key(self, tenant_id: str, doc_id: str) -> str:
        """Build cache key for a single document."""
        return f"v1:doc:{tenant_id}:{doc_id}"
    
    async def get_cached_search(
        self,
        tenant_id: str,
        query: str,
        offset: int,
        limit: int
    ) -> Optional[dict]:
        """
        Retrieve cached search results.
        
        Returns None on cache miss OR if Redis is unavailable (graceful degradation).
        """
        try:
            key = self._build_search_key(tenant_id, query, offset, limit)
            cached = await self.client.get(key)
            if cached:
                logger.debug(f"Cache HIT for {key}")
                return json.loads(cached)
            logger.debug(f"Cache MISS for {key}")
            return None
        except Exception as e:
            # Graceful degradation — don't fail requests due to cache issues
            logger.warning(f"Redis error (ignoring): {e}")
            return None
    
    async def set_cached_search(
        self,
        tenant_id: str,
        query: str,
        offset: int,
        limit: int,
        results: dict
    ):
        """Cache search results with TTL."""
        try:
            key = self._build_search_key(tenant_id, query, offset, limit)
            await self.client.setex(
                key,
                settings.CACHE_TTL_SEARCH,
                json.dumps(results, default=str)
            )
            logger.debug(f"Cached results for {key}")
        except Exception as e:
            logger.warning(f"Failed to cache: {e}")
    
    async def invalidate_tenant_search_cache(self, tenant_id: str):
        """
        Invalidate all search caches for a tenant.
        
        Called when a document is added/deleted to prevent stale results.
        """
        try:
            pattern = f"v1:search:{tenant_id}:*"
            async for key in self.client.scan_iter(match=pattern):
                await self.client.delete(key)
            logger.info(f"Invalidated search cache for tenant {tenant_id}")
        except Exception as e:
            logger.warning(f"Cache invalidation failed: {e}")
    
    async def check_rate_limit(
        self,
        tenant_id: str,
        limit_per_minute: int = 60
    ) -> tuple[bool, int]:
        """
        Check if tenant has exceeded rate limit.
        
        Uses a sliding window with 1-minute buckets.
        Returns (allowed, remaining_requests).
        """
        try:
            import time
            current_minute = int(time.time() // 60)
            key = f"v1:ratelimit:{tenant_id}:{current_minute}"
            
            # Atomic increment
            current_count = await self.client.incr(key)
            
            # Set expiry on first increment
            if current_count == 1:
                await self.client.expire(key, 60)
            
            remaining = max(0, limit_per_minute - current_count)
            allowed = current_count <= limit_per_minute
            
            return allowed, remaining
        except Exception as e:
            # On Redis failure, allow the request (fail open)
            logger.warning(f"Rate limit check failed: {e}")
            return True, limit_per_minute
    
    async def health_check(self) -> dict:
        """Check Redis health."""
        try:
            await self.client.ping()
            return {"status": "healthy"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


# Singleton instance
redis_service = RedisService()