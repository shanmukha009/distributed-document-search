"""Document CRUD endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Header, status

from src.models.document import (
    DocumentCreate,
    DocumentResponse,
    DocumentDetail,
    DocumentStatus
)
from src.services.elasticsearch_service import es_service
from src.services.postgres_service import pg_service
from src.services.redis_service import redis_service
from src.config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/documents", tags=["documents"])


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


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_document(
    document: DocumentCreate,
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID")
):
    """
    Index a new document.
    
    Returns 202 Accepted immediately. The document is indexed synchronously
    in this prototype (production would use async workers via RabbitMQ).
    """
    tenant_id = _validate_tenant(x_tenant_id)
    
    # Rate limiting check
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
    
    try:
        # 1. Index in Elasticsearch first (get doc_id)
        doc_id = await es_service.index_document(
            tenant_id=tenant_id,
            title=document.title,
            content=document.content,
            metadata=document.metadata
        )
        
        # 2. Store metadata in PostgreSQL (source of truth)
        await pg_service.create_document_metadata(
            doc_id=doc_id,
            tenant_id=tenant_id,
            title=document.title,
            metadata=document.metadata
        )
        
        # 3. Update status to indexed
        await pg_service.update_document_status(
            doc_id=doc_id,
            tenant_id=tenant_id,
            status="indexed"
        )
        
        # 4. Invalidate search cache (new document changes results)
        await redis_service.invalidate_tenant_search_cache(tenant_id)
        
        return DocumentResponse(
            document_id=doc_id,
            status=DocumentStatus.INDEXED,
            message="Document indexed successfully",
            estimated_indexing_time_seconds=0
        )
    
    except Exception as e:
        logger.error(f"Failed to index document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INDEXING_FAILED",
                    "message": "Failed to index document",
                    "details": {"error": str(e)}
                }
            }
        )


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: str,
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID")
):
    """Retrieve document details by ID."""
    tenant_id = _validate_tenant(x_tenant_id)
    
    # Get from Elasticsearch (has full content)
    doc_es = await es_service.get_document(tenant_id, document_id)
    if not doc_es:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": "Document not found"
                }
            }
        )
    
    # Get metadata from PostgreSQL
    doc_pg = await pg_service.get_document_metadata(document_id, tenant_id)
    
    return DocumentDetail(
        document_id=document_id,
        tenant_id=tenant_id,
        title=doc_es.get("title", ""),
        content=doc_es.get("content", ""),
        metadata=doc_es.get("metadata", {}),
        status=doc_pg["status"] if doc_pg else "indexed",
        created_at=doc_pg["created_at"] if doc_pg else doc_es.get("created_at"),
        indexed_at=doc_pg["indexed_at"] if doc_pg else None
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID")
):
    """Delete a document."""
    tenant_id = _validate_tenant(x_tenant_id)
    
    # Delete from Elasticsearch
    es_deleted = await es_service.delete_document(tenant_id, document_id)
    
    # Soft delete in PostgreSQL
    pg_deleted = await pg_service.delete_document_metadata(document_id, tenant_id)
    
    if not es_deleted and not pg_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": "Document not found"
                }
            }
        )
    
    # Invalidate cache
    await redis_service.invalidate_tenant_search_cache(tenant_id)
    
    return None