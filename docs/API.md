# Step 2 API — Simplified Knowledge Indexing Service

## Authentication
- Header: `X-API-Key: <key>`
- Missing/invalid key -> `401`
- Valid key but tenant not authorized -> `403`
- Tenant is `{tenantId}` path param; must be allowed for key.
- Config via env `API_KEYS_JSON` mapping key -> list of tenants.

---

## 1) Ingest Document
**POST** `/api/v1/tenants/{tenantId}/documents`

Headers:
- `X-API-Key: ...`
- `Content-Type: application/json`

Request body:
```json
{
  "title": "Doc title",
  "content": "Plain text content ...",
  "tags": ["tag1", "tag2"]
}
```

Response `201`:
```json
{
  "documentId": "uuid-or-ulid",
  "tenantId": "t1",
  "createdAt": "2026-01-18T12:34:56Z"
}
```

Errors:
- `400` invalid body/limits
- `401` missing/invalid key
- `403` tenant not authorized
- `500` internal

---

## 2) Search Documents (ranked)
**GET** `/api/v1/tenants/{tenantId}/documents/search?q={query}&limit={n}&offset={n}`

Headers:
- `X-API-Key: ...`

Query params:
- `q` (required): search query string
- `limit` (optional): default 10, max 50
- `offset` (optional): default 0

Response `200`:
```json
{
  "tenantId": "t1",
  "query": "observability platform",
  "limit": 10,
  "offset": 0,
  "total": 123,
  "results": [
    {
      "documentId": "uuid",
      "title": "....",
      "snippet": "short snippet around match",
      "tags": ["tag1"],
      "score": 2.345,
      "createdAt": "2026-01-18T12:34:56Z"
    }
  ]
}
```

Notes:
- Results must be tenant-scoped.
- Rank by FTS5 relevance (bm25). API `score` must be **higher = better**.

Errors:
- `400` if q missing/blank
- `401/403` auth issues
- `500` internal

---

## 3) Health
**GET** `/api/v1/health`

Auth: not required (recommended for ops simplicity).

Response `200`:
```json
{
  "status": "ok",
  "time": "2026-01-18T12:34:56Z"
}
```

---

## 4) Metrics
**GET** `/api/v1/metrics`

Auth: not required (recommended for ops simplicity).

Response `200` (JSON):
```json
{
  "uptimeSeconds": 1234,
  "requests": {
    "total": 1000,
    "byTenant": {
      "t1": 700,
      "t2": 300
    },
    "byEndpoint": {
      "POST /api/v1/tenants/{tenantId}/documents": 200,
      "GET /api/v1/tenants/{tenantId}/documents/search": 800,
      "GET /api/v1/health": 10,
      "GET /api/v1/metrics": 5
    }
  },
  "latencyMs": {
    "avgOverall": 12.3,
    "byEndpointAvg": {
      "GET /api/v1/tenants/{tenantId}/documents/search": 18.7
    }
  },
  "errors": {
    "total": 12,
    "byStatus": { "400": 5, "401": 2, "403": 1, "500": 4 },
    "byTenant": { "t1": 9, "t2": 3 }
  },
  "documents": {
    "byTenant": { "t1": 5432, "t2": 4568 }
  }
}
```

Collection rules:
- Count every request (including errors).
- Latency is wall-time; maintain sum/count per endpoint.
- Error counters by status and by tenant (if tenant determined).
- Document counts from DB aggregation (or cached refresh).
