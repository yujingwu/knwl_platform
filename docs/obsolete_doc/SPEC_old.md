# Step 2 SPEC — Simplified Knowledge Indexing Service (FastAPI + SQLite FTS5)

## Purpose
This spec is the single source of truth for **Part 2: Core Implementation** of the coding assessment: implement a simplified knowledge indexing service with 3 features (ingest, search, health/metrics) using an embedded database or in-memory storage.

## Goals
- **Ingest** documents per tenant
- **Text-based search** per tenant with ranked results and pagination
- **Health** endpoint
- **Metrics** endpoint with per-tenant breakdowns
- **Auth middleware**: API-key based; validates tenant authorization
- Embedded storage: **SQLite** with **FTS5** for indexing/search
- Tests: unit + integration, **>70% coverage**
- Performance: search **p95 < 100ms** at **10,000 docs** (include benchmark script)
- OpenAPI/Swagger available from FastAPI
- Clear setup instructions + curl examples in `README.md`

## Non-goals
- Semantic search / embeddings (belongs to Part 1 design)
- Queues/object store/async pipeline (Part 1 concepts only)

## Stack (Part 2)
- Python 3.x
- FastAPI + Pydantic
- SQLite file DB + FTS5 virtual table
- pytest + pytest-cov
- Optional: Docker (not required for Step 2, but OK)

## Configuration (env vars)
- `DB_PATH` default `./data/app.db`
- `API_KEYS_JSON` JSON string mapping API key -> list of tenant IDs (required for local dev)
  - Example: `{"key_admin":["t1","t2"],"key_t1":["t1"]}`
- `MAX_TITLE_LEN` default `200`
- `MAX_CONTENT_LEN` default `200000`
- `MAX_TAGS` default `20`
- `LOG_LEVEL` default `INFO`

## Auth model
- Header: `X-API-Key: <key>`
- Missing/invalid key -> `401`
- Valid key but tenant not allowed -> `403`
- Tenant comes from path param `{tenantId}` and is validated against the API key’s allowed tenants.

## Data model
### documents table
- `tenant_id TEXT NOT NULL`
- `document_id TEXT NOT NULL` (UUID/ULID)
- `title TEXT NOT NULL`
- `content TEXT NOT NULL`
- `tags TEXT NOT NULL` (JSON array string)
- `created_at TEXT NOT NULL` (ISO8601)
- `updated_at TEXT NOT NULL` (ISO8601)
- Primary key: `(tenant_id, document_id)`
- Index: `idx_documents_tenant_created (tenant_id, created_at DESC)`

### documents_fts virtual table (FTS5 external content)
- Includes: `tenant_id UNINDEXED`, `title`, `content`, `tags`
- Maintained with triggers on insert/update/delete

## Search semantics
- Endpoint uses SQLite FTS5 `MATCH` and ranks by `bm25()`.
- API returns `score` where **higher = more relevant**.
  - If bm25 is smaller-is-better, transform: `score = 1.0 / (1.0 + bm25)`.
- Include `snippet()` for highlighted snippet in results.
- Pagination: `limit` (default 10, max 50), `offset` (default 0).
- Compute `total` as `COUNT(*)` on same match (acceptable at 10K docs).

## Observability requirements
- Generate/propagate `X-Request-Id`:
  - Use client-provided header if present, else generate UUID.
- Structured logs per request: request_id, tenant_id (if available), method, path, status, latency_ms.

## Benchmark
Create `scripts/benchmark.py`:
- Populate 10,000 docs for one tenant
- Warm up ~20 queries
- Measure p50/p95 for search endpoint across 200–1000 queries
- Print results; assert p95 < 100ms (configurable threshold)
- Use either in-process `TestClient` or `httpx` against a running server; document approach in README.

## Repo structure (recommended)
```
repo/
  app/
    __init__.py
    main.py
    api/
      routes_docs.py
      routes_search.py
      routes_health.py
      routes_metrics.py
    core/
      config.py
      auth.py
      metrics.py
      logging.py
    db/
      sqlite.py
      schema.py
      repo.py
    models/
      schemas.py
  scripts/
    benchmark.py
  tests/
    test_auth.py
    test_ingest.py
    test_search.py
    test_metrics.py
  requirements.txt (or pyproject.toml)
  README.md
  docs/
    SPEC.md
    API.md
    DESIGN.md
    DECISIONS.md
```

## Acceptance checklist
- [ ] Ingest returns `201` with `documentId`
- [ ] Search returns ranked results with `score` and `snippet`
- [ ] Tenant isolation is enforced (no cross-tenant leakage)
- [ ] `/health` returns 200 ok
- [ ] `/metrics` returns JSON with required counters (see API.md)
- [ ] Tests pass; coverage > 70%
- [ ] Benchmark demonstrates p95 < 100ms @ 10K docs
- [ ] README includes setup + curl examples + test/benchmark commands
