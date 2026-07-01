"""Document data models."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class DocumentStatus(str, Enum):
    """Document indexing status."""
    PENDING = "pending"
    INDEXED = "indexed"
    FAILED = "failed"
    DELETED = "deleted"


class DocumentCreate(BaseModel):
    """Request model for creating a new document."""
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    metadata: Optional[dict] = Field(default_factory=dict)


class DocumentResponse(BaseModel):
    """Response model when creating a document."""
    document_id: str
    status: DocumentStatus
    message: str
    estimated_indexing_time_seconds: int = 3


class DocumentDetail(BaseModel):
    """Full document details."""
    document_id: str
    tenant_id: str
    title: str
    content: str
    metadata: dict
    status: DocumentStatus
    created_at: datetime
    indexed_at: Optional[datetime] = None


class SearchResult(BaseModel):
    """A single search result."""
    document_id: str
    title: str
    snippet: str
    score: float
    metadata: dict
    created_at: datetime


class SearchResponse(BaseModel):
    """Response model for search queries."""
    total: int
    limit: int
    offset: int
    took_ms: int
    cached: bool
    results: list[SearchResult]


class ErrorResponse(BaseModel):
    """Standard error response format."""
    error: dict


class HealthStatus(BaseModel):
    """Health check response."""
    status: str
    version: str
    timestamp: datetime
    dependencies: dict