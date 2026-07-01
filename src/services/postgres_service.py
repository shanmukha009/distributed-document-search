"""PostgreSQL service for document metadata storage."""

import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import Column, DateTime, String, Text, JSON, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

from src.config.settings import settings

logger = logging.getLogger(__name__)

Base = declarative_base()


class DocumentMetadata(Base):
    """
    Document metadata table.
    
    Stores the source of truth for document existence.
    Multi-tenancy enforced via tenant_id column with application-level filtering.
    """
    __tablename__ = "documents"
    
    id = Column(String(50), primary_key=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    doc_metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    indexed_at = Column(DateTime, nullable=True)


class PostgresService:
    """Handles PostgreSQL operations for document metadata."""
    
    def __init__(self):
        self.engine = None
        self.session_factory = None
    
    async def connect(self):
        """Initialize PostgreSQL connection and create tables."""
        self.engine = create_async_engine(
            settings.DATABASE_URL,
            echo=False,
            pool_size=10,
            max_overflow=20
        )
        
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # Create tables if they don't exist
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("Connected to PostgreSQL")
    
    async def disconnect(self):
        """Close PostgreSQL connection."""
        if self.engine:
            await self.engine.dispose()
    
    async def create_document_metadata(
        self,
        doc_id: str,
        tenant_id: str,
        title: str,
        metadata: dict
    ):
        """Insert new document metadata."""
        async with self.session_factory() as session:
            doc = DocumentMetadata(
                id=doc_id,
                tenant_id=tenant_id,
                title=title,
                status="pending",
                doc_metadata=metadata,
                created_at=datetime.utcnow()
            )
            session.add(doc)
            await session.commit()
            logger.info(f"Created metadata for doc {doc_id}, tenant {tenant_id}")
    
    async def update_document_status(
        self,
        doc_id: str,
        tenant_id: str,
        status: str
    ):
        """Update document indexing status."""
        async with self.session_factory() as session:
            stmt = select(DocumentMetadata).where(
                DocumentMetadata.id == doc_id,
                DocumentMetadata.tenant_id == tenant_id
            )
            result = await session.execute(stmt)
            doc = result.scalar_one_or_none()
            
            if doc:
                doc.status = status
                if status == "indexed":
                    doc.indexed_at = datetime.utcnow()
                await session.commit()
    
    async def get_document_metadata(
        self,
        doc_id: str,
        tenant_id: str
    ) -> Optional[dict]:
        """
        Retrieve document metadata.
        
        Multi-tenancy: Always filter by tenant_id.
        """
        async with self.session_factory() as session:
            stmt = select(DocumentMetadata).where(
                DocumentMetadata.id == doc_id,
                DocumentMetadata.tenant_id == tenant_id  # Tenant isolation!
            )
            result = await session.execute(stmt)
            doc = result.scalar_one_or_none()
            
            if not doc:
                return None
            
            return {
                "document_id": doc.id,
                "tenant_id": doc.tenant_id,
                "title": doc.title,
                "status": doc.status,
                "metadata": doc.doc_metadata,
                "created_at": doc.created_at,
                "indexed_at": doc.indexed_at
            }
    
    async def delete_document_metadata(
        self,
        doc_id: str,
        tenant_id: str
    ) -> bool:
        """Soft-delete a document (mark as deleted)."""
        async with self.session_factory() as session:
            stmt = select(DocumentMetadata).where(
                DocumentMetadata.id == doc_id,
                DocumentMetadata.tenant_id == tenant_id
            )
            result = await session.execute(stmt)
            doc = result.scalar_one_or_none()
            
            if not doc:
                return False
            
            doc.status = "deleted"
            await session.commit()
            return True
    
    async def health_check(self) -> dict:
        """Check PostgreSQL health."""
        try:
            async with self.session_factory() as session:
                await session.execute(select(1))
            return {"status": "healthy"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


# Singleton instance
pg_service = PostgresService()