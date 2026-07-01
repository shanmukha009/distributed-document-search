# Distributed Document Search Service

Enterprise-grade multi-tenant document search service with sub-second response times. Designed to handle 10+ million documents across multiple tenants with strict data isolation.

**Author:** Shanmukha Raj  
**Date:** July 2026  
**Status:** Prototype (Assessment Submission for DeepRunner AI)

---

## Overview

A distributed document search service built with FastAPI, Elasticsearch, Redis, and PostgreSQL. Designed for enterprise SaaS use cases where multiple customers need isolated document repositories with fast, relevant search.

**Key Capabilities:**
- Full-text search with BM25 relevance ranking
- Multi-tenant architecture with strict data isolation
- Sub-500ms search latency (with Redis caching)
- Rate limiting per tenant
- Health monitoring with dependency status
- Horizontal scalability

---

## Quick Start

**Prerequisites:** Docker Desktop installed

```bash
git clone https://github.com/shanmukha009/distributed-document-search.git
cd distributed-document-search
docker-compose up --build
```

The service will be available at:
- API: `http://localhost:8000`
- Interactive API Docs: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/health`

Wait for the log message `Application startup complete` before making requests.

---

## Architecture

```
Client
  |
  v
FastAPI Application (Multi-tenancy, Rate limiting, Validation)
  |
  |---> Redis Cache (Query results, TTL 60s)
  |
  |---> Elasticsearch (Full-text search, tenant-scoped indices)
  |
  |---> PostgreSQL (Metadata, source of truth)
```

See `docs/ARCHITECTURE.md` for the complete architecture design document covering:
- System components and their responsibilities
- Data flow diagrams (indexing and search)
- Storage strategy and database choices
- API design and error handling
- Caching strategy (multi-layer)
- Message queue usage (RabbitMQ)
- Multi-tenancy deep dive
- Consistency model and trade-offs

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| API Framework | FastAPI | REST API with automatic OpenAPI docs |
| Search Engine | Elasticsearch 8.15 | Full-text search with relevance ranking |
| Cache | Redis 7.4 | Query result caching and rate limiting |
| Metadata Store | PostgreSQL 15 | Source of truth for document metadata |
| Container Runtime | Docker Compose | Multi-service orchestration |
| Language | Python 3.11 | Application code |

---

## API Endpoints

### Index a Document

```http
POST /v1/documents
X-Tenant-ID: disney_corp
Content-Type: application/json

{
  "title": "Marvel Studios Q3 2024 Contract",
  "content": "This agreement between Marvel Studios and Disney...",
  "metadata": {
    "author": "Legal Team",
    "tags": ["contract", "marvel"]
  }
}
```

Response (202 Accepted):
```json
{
  "document_id": "doc_abc123def456",
  "status": "indexed",
  "message": "Document indexed successfully",
  "estimated_indexing_time_seconds": 0
}
```

### Search Documents

```http
GET /v1/search?q=marvel&limit=10&offset=0
X-Tenant-ID: disney_corp
```

Response (200 OK):
```json
{
  "total": 6,
  "limit": 10,
  "offset": 0,
  "took_ms": 45,
  "cached": false,
  "results": [
    {
      "document_id": "doc_abc123def456",
      "title": "Marvel Studios Q3 2024 Contract",
      "snippet": "This agreement between <em>Marvel</em> Studios and Disney...",
      "score": 1.8455076,
      "metadata": {...},
      "created_at": "2026-07-01T20:43:22.799446"
    }
  ]
}
```

### Retrieve a Document

```http
GET /v1/documents/{document_id}
X-Tenant-ID: disney_corp
```

### Delete a Document

```http
DELETE /v1/documents/{document_id}
X-Tenant-ID: disney_corp
```

Response: 204 No Content

### Health Check

```http
GET /health
```

Response includes status of all dependencies (Elasticsearch, Redis, PostgreSQL).

---

## Sample cURL Commands

### Index a document
```bash
curl -X POST http://localhost:8000/v1/documents \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: disney_corp" \
  -d '{
    "title": "Marvel Studios Q3 2024 Contract",
    "content": "This agreement between Marvel Studios and Disney regarding the Avengers franchise",
    "metadata": {"author": "Legal Team", "tags": ["contract", "marvel"]}
  }'
```

### Search
```bash
curl "http://localhost:8000/v1/search?q=marvel" \
  -H "X-Tenant-ID: disney_corp"
```

### Verify multi-tenancy isolation (should return 0 results)
```bash
curl "http://localhost:8000/v1/search?q=marvel" \
  -H "X-Tenant-ID: netflix_corp"
```

### Get document by ID
```bash
curl "http://localhost:8000/v1/documents/doc_abc123def456" \
  -H "X-Tenant-ID: disney_corp"
```

### Delete document
```bash
curl -X DELETE "http://localhost:8000/v1/documents/doc_abc123def456" \
  -H "X-Tenant-ID: disney_corp"
```

---

## Multi-Tenancy Design

Multi-tenancy is enforced at three layers for defense in depth:

**Layer 1: Elasticsearch**  
Each tenant gets a dedicated index named `tenant_{tenant_id}_docs`. Queries are physically scoped to the tenant's index, making cross-tenant queries impossible.

**Layer 2: PostgreSQL**  
Every table includes a `tenant_id` column. All queries filter by tenant_id. In production, this is enforced by Row-Level Security policies.

**Layer 3: Redis Cache**  
All cache keys are namespaced with tenant_id (e.g., `v1:search:disney_corp:query_hash`). This prevents cache-level data leakage between tenants.

---

## Caching Strategy

The system uses the **cache-aside pattern**:

1. Search request arrives
2. Check Redis for cached result
3. On cache HIT: return cached result (1ms response)
4. On cache MISS: query Elasticsearch (45ms), cache result with 60s TTL, return

**Observed performance:**
- Cache HIT: ~1-23ms
- Cache MISS: ~45-100ms
- Both well under the 500ms target

**Cache invalidation:** When a document is added or deleted, all search caches for that tenant are invalidated to prevent stale results.

---

## Rate Limiting

Rate limiting is enforced per tenant using Redis-based sliding window counters:

- Free tier: 60 requests/minute
- Pro tier: 600 requests/minute
- Enterprise tier: 6000 requests/minute

When exceeded, the API returns 429 Too Many Requests with retry information.

---

## Project Structure

```
distributed-document-search/
├── docs/
│   ├── ARCHITECTURE.md          Complete architecture design document
│   ├── EXPERIENCE_SHOWCASE.md   Enterprise experience examples
│   └── PRODUCTION_READINESS.md  Production readiness analysis
├── src/
│   ├── main.py                  FastAPI application entry point
│   ├── api/
│   │   ├── documents.py         Document CRUD endpoints
│   │   ├── search.py            Search endpoint
│   │   └── health.py            Health check endpoints
│   ├── services/
│   │   ├── elasticsearch_service.py
│   │   ├── redis_service.py
│   │   └── postgres_service.py
│   ├── models/
│   │   └── document.py          Pydantic data models
│   └── config/
│       └── settings.py          Configuration management
├── tests/                       Test files (placeholder)
├── docker-compose.yml           Multi-service orchestration
├── Dockerfile                   Application container
├── requirements.txt             Python dependencies
└── README.md                    This file
```

---

## Design Decisions and Trade-offs

Key architectural decisions and their reasoning:

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| Elasticsearch for search | Built for 10M+ documents, distributed by design | Additional operational complexity |
| PostgreSQL for metadata | ACID guarantees for source of truth | Slower than NoSQL alternatives |
| Redis for caching | Sub-millisecond latency, mature ecosystem | Additional dependency to maintain |
| Index-per-tenant | Strict data isolation, easy per-tenant operations | Overhead for very small tenants |
| Header-based multi-tenancy | Clean URLs, industry standard (Stripe, Twilio) | Requires application-level enforcement |
| Cache-aside pattern | Simple, only caches active data | Cold start on first request |
| Eventual consistency for search | Enables async processing and horizontal scaling | 1-5 second indexing delay |

Full trade-off analysis is documented in `docs/ARCHITECTURE.md`.

---

## Production Readiness

This is a **prototype**, not production-ready code. See `docs/PRODUCTION_READINESS.md` for a detailed analysis of what would be required for production deployment, including:

- Scalability considerations for 100x growth
- Resilience patterns (circuit breakers, retries, failover)
- Security hardening (authentication, encryption, API security)
- Observability (metrics, logging, distributed tracing)
- Performance optimization strategies
- Operations (deployment, backup, recovery)
- SLA considerations for 99.95% availability

---

## AI Tool Usage

Following the assessment guidance, AI tools (Claude, ChatGPT) were used during development for:

- Brainstorming alternative architectural patterns
- Sanity-checking trade-off analysis
- Drafting initial versions of documentation
- Generating boilerplate code

All architectural decisions, code review, and testing were performed by the author. The prototype was verified end-to-end using both cURL commands and the interactive Swagger UI at `/docs`.

---

## Testing the Prototype

After running `docker-compose up --build`, verify the system with these tests:

**Test 1: Health check**
```bash
curl http://localhost:8000/health
```
Expected: All dependencies healthy

**Test 2: Upload and search**
```bash
# Upload
curl -X POST http://localhost:8000/v1/documents \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: disney_corp" \
  -d '{"title":"Test","content":"marvel test content","metadata":{}}'

# Search
curl "http://localhost:8000/v1/search?q=marvel" -H "X-Tenant-ID: disney_corp"
```

**Test 3: Verify caching (second search should show cached: true)**
```bash
curl "http://localhost:8000/v1/search?q=marvel" -H "X-Tenant-ID: disney_corp"
```

**Test 4: Verify tenant isolation (should return 0 results)**
```bash
curl "http://localhost:8000/v1/search?q=marvel" -H "X-Tenant-ID: netflix_corp"
```

---

## Documentation

- **ARCHITECTURE.md** — Complete 10-section architecture design document
- **PRODUCTION_READINESS.md** — Production readiness analysis
- **EXPERIENCE_SHOWCASE.md** — Enterprise experience examples

---

## License

MIT License — see LICENSE file for details.