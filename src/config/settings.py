"""Application configuration settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Environment variables take precedence over defaults.
    """
    
    # Application
    APP_NAME: str = "Distributed Document Search"
    APP_VERSION: str = "1.0.0"
    LOG_LEVEL: str = "INFO"
    
    # Elasticsearch
    ELASTICSEARCH_URL: str = "http://localhost:9200"
    ES_INDEX_PREFIX: str = "tenant_"
    ES_INDEX_SUFFIX: str = "_docs"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_SEARCH: int = 60  # 60 seconds
    CACHE_TTL_DOCUMENT: int = 300  # 5 minutes
    
    # PostgreSQL
    DATABASE_URL: str = "postgresql+asyncpg://docsearch:docsearch_password@localhost:5432/documents_db"
    
    # Rate Limiting
    RATE_LIMIT_FREE: int = 60  # requests per minute
    RATE_LIMIT_PRO: int = 600
    RATE_LIMIT_ENTERPRISE: int = 6000
    
    # Multi-tenancy
    TENANT_HEADER: str = "X-Tenant-ID"
    
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


# Singleton settings instance
settings = Settings()