"""Elasticsearch service for document indexing and search."""

import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from elasticsearch import AsyncElasticsearch, NotFoundError

from src.config.settings import settings

logger = logging.getLogger(__name__)


class ElasticsearchService:
    """
    Handles all Elasticsearch operations.
    
    Multi-tenancy strategy: Each tenant gets a dedicated index
    named `tenant_{tenant_id}_docs` for strict data isolation.
    """
    
    def __init__(self):
        self.client: Optional[AsyncElasticsearch] = None
    
    async def connect(self):
        """Initialize Elasticsearch connection."""
        self.client = AsyncElasticsearch([settings.ELASTICSEARCH_URL])
        logger.info(f"Connected to Elasticsearch at {settings.ELASTICSEARCH_URL}")
    
    async def disconnect(self):
        """Close Elasticsearch connection."""
        if self.client:
            await self.client.close()
    
    def _get_index_name(self, tenant_id: str) -> str:
        """
        Generate tenant-scoped index name.
        
        This is our multi-tenancy security boundary — each tenant
        gets a dedicated index, so cross-tenant queries are impossible.
        """
        return f"{settings.ES_INDEX_PREFIX}{tenant_id}{settings.ES_INDEX_SUFFIX}"
    
    async def ensure_tenant_index(self, tenant_id: str):
        """
        Create the tenant's index if it doesn't exist.
        
        This is called lazily on first document upload.
        In production, this would be called during tenant onboarding.
        """
        index_name = self._get_index_name(tenant_id)
        
        if not await self.client.indices.exists(index=index_name):
            await self.client.indices.create(
                index=index_name,
                body={
                    "settings": {
                        "number_of_shards": 3,
                        "number_of_replicas": 1,
                        "analysis": {
                            "analyzer": {
                                "default": {"type": "standard"}
                            }
                        }
                    },
                    "mappings": {
                        "properties": {
                            "title": {
                                "type": "text",
                                "fields": {"keyword": {"type": "keyword"}}
                            },
                            "content": {"type": "text"},
                            "metadata": {"type": "object", "dynamic": True},
                            "created_at": {"type": "date"}
                        }
                    }
                }
            )
            logger.info(f"Created index: {index_name}")
    
    async def index_document(
        self,
        tenant_id: str,
        title: str,
        content: str,
        metadata: dict
    ) -> str:
        """
        Index a new document for a tenant.
        
        Returns the generated document ID.
        """
        await self.ensure_tenant_index(tenant_id)
        
        doc_id = f"doc_{uuid4().hex[:16]}"
        index_name = self._get_index_name(tenant_id)
        
        await self.client.index(
            index=index_name,
            id=doc_id,
            body={
                "title": title,
                "content": content,
                "metadata": metadata,
                "created_at": datetime.utcnow().isoformat()
            },
            refresh=False  # Async refresh for performance
        )
        
        logger.info(f"Indexed doc {doc_id} for tenant {tenant_id}")
        return doc_id
    
    async def search(
        self,
        tenant_id: str,
        query: str,
        limit: int = 10,
        offset: int = 0
    ) -> dict:
        """
        Full-text search across the tenant's documents.
        
        Uses Elasticsearch's BM25 relevance ranking by default.
        Returns highlighted snippets showing where the match occurred.
        """
        index_name = self._get_index_name(tenant_id)
        
        try:
            response = await self.client.search(
                index=index_name,
                body={
                    "from": offset,
                    "size": limit,
                    "query": {
                        "multi_match": {
                            "query": query,
                            "fields": ["title^2", "content"],  # title 2x weight
                            "fuzziness": "AUTO"
                        }
                    },
                    "highlight": {
                        "fields": {
                            "content": {
                                "fragment_size": 150,
                                "number_of_fragments": 1
                            }
                        },
                        "pre_tags": ["<em>"],
                        "post_tags": ["</em>"]
                    }
                }
            )
        except NotFoundError:
            # Tenant index doesn't exist yet
            return {"total": 0, "results": []}
        
        results = []
        for hit in response["hits"]["hits"]:
            source = hit["_source"]
            snippet = source.get("content", "")[:150]
            
            # Use highlighted snippet if available
            if "highlight" in hit and "content" in hit["highlight"]:
                snippet = hit["highlight"]["content"][0]
            
            results.append({
                "document_id": hit["_id"],
                "title": source.get("title", ""),
                "snippet": snippet,
                "score": hit["_score"],
                "metadata": source.get("metadata", {}),
                "created_at": source.get("created_at", "")
            })
        
        return {
            "total": response["hits"]["total"]["value"],
            "took_ms": response["took"],
            "results": results
        }
    
    async def get_document(self, tenant_id: str, doc_id: str) -> Optional[dict]:
        """Retrieve a specific document by ID."""
        index_name = self._get_index_name(tenant_id)
        
        try:
            response = await self.client.get(index=index_name, id=doc_id)
            return {
                "document_id": response["_id"],
                **response["_source"]
            }
        except NotFoundError:
            return None
    
    async def delete_document(self, tenant_id: str, doc_id: str) -> bool:
        """Delete a document from the tenant's index."""
        index_name = self._get_index_name(tenant_id)
        
        try:
            await self.client.delete(index=index_name, id=doc_id)
            logger.info(f"Deleted doc {doc_id} from tenant {tenant_id}")
            return True
        except NotFoundError:
            return False
    
    async def health_check(self) -> dict:
        """Check Elasticsearch cluster health."""
        try:
            health = await self.client.cluster.health()
            return {
                "status": "healthy",
                "cluster_status": health["status"],
                "number_of_nodes": health["number_of_nodes"]
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


# Singleton instance
es_service = ElasticsearchService()