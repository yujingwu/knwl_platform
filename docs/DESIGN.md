# Step 2 DESIGN (Simplified Implementation)

## Purpose
This document describes the **Part 2 simplified service** only. The production-grade, cloud-agnostic platform design (Part 1) is separate and may include semantic search, async pipelines, and additional components not implemented here.

## Architecture (Part 2)
- Single FastAPI service
- Embedded SQLite database
- SQLite FTS5 virtual table for text search
- In-process metrics collection

### Diagram
```
Client (HTTP + X-API-Key)
  |
  v
FastAPI Service
  |-- Auth middleware (API key -> allowed tenants)
  |-- Ingest endpoint -> SQLite documents + FTS5 index
  |-- Search endpoint -> FTS5 MATCH + bm25 ranking + snippet
  |-- /health
  |-- /metrics (JSON)
  v
SQLite (documents table + documents_fts)
```

## Data flow (Part 2)
1) **Ingest**: client POSTs doc -> auth validates tenant -> store in `documents` -> update `documents_fts` -> return `documentId`.
2) **Search**: client GETs search -> auth validates tenant -> FTS5 MATCH + rank/snippet -> return results.
3) **Ops**: `/health` reports readiness; `/metrics` reports counters/latency/errors/doc counts.

## Scalability/Performance notes
- Target dataset is 10K docs; SQLite+FTS5 is sufficient.
- A benchmark script validates p95 < 100ms on the search endpoint.
