# Design Doc — Scalable Multi-Tenant Knowledge Indexing Platform (Cloud-Agnostic)

## 0. Scope and Goals
Build a scalable, multi-tenant knowledge indexing platform that supports:
- Ingest documents (PDF/text/structured), index them, and serve search
- **Fast retrieval via semantic search** (embeddings + vector retrieval)
- Multi-tenant isolation
- High availability + fault tolerance
- Scale targets: **100K docs/day ingestion**, **10K concurrent queries**, plus a caching strategy

Non-goals (for this design doc):
- Training custom ML models (use pretrained embeddings)
- Cross-region active-active (can be future work)

---

## 1) Architecture Diagram and Data Flow

### Major Components
- **API Edge**: gateway/L7 LB, WAF, rate limiting, request routing
- **AuthN/AuthZ**: validates JWT/OAuth/API key → derives `tenant_id`, `actor_id`, roles
- **Ingestion API**: accepts docs + metadata, validates, writes metadata, stores raw content, enqueues indexing
- **Object Store**: raw docs + normalized text artifacts
- **Metadata Store**: doc metadata + processing state + idempotency
- **Queue + DLQ**: decouple ingest from indexing
- **Indexing Workers**: extract → chunk → embed → index (lexical + vector)
- **Embedding Service**: hosted API or self-hosted embedding model server
- **Search API**: hybrid retrieval (vector + lexical), filtering, pagination, ranking
- **Search Index**:
  - **Vector index** (ANN) for semantic search
  - **Lexical index** (BM25/FTS) for keyword search
- **Cache**: query/result cache + hot metadata cache
- **Audit Log Store**: append-only compliance logging
- **Observability**: logs/metrics/traces

### High-Level Architecture Diagram with Data Flow

```
                           +------------------------------+
                           |     API Edge (WAF, RL)       |
Clients (UI/SDK) --------->|  Gateway / LB / Rate Limits  |
                           +---------------+--------------+
                                           |
                                      (1) HTTPS
                                           |
                                           v
                           +------------------------------+
                           |        AuthN / AuthZ / RBAC  |
                           |  JWT/OAuth/API key -> tenant |
                           +---------------+--------------+
                                           |
                       +-------------------+-------------------+
                       |                                       |
              Ingestion Path                               Query Path
                       |                                       |
                       v                                       v
+----------------------+------------------+      +---------------------------+
|         Ingestion API                    |      |         Search API        |
| validate, size limits, idempotency key   |      | hybrid retrieval, filters |
+-----------+------------------------------+      +------------+--------------+
            |                                            (10)  |
    (2) metadata write                                           | cache lookup
            v                                                    v
+--------------------------+                           +-----------------------+
|      Metadata Store      |<--------------------------|         Cache         |
| doc_id, tenant_id, state |                           | results + hot metadata|
+-----------+--------------+                           +----------+------------+
            |
 (3) store raw/normalized text
            v
+--------------------------+
|       Object Store       |
| raw docs + extracted text|
+-----------+--------------+
            |
  (4) enqueue indexing job
            v
+--------------------------+
|    Queue (w/ DLQ)        |
+-----------+--------------+
            |
     (5) consume + process
            v
+--------------------------+         (7) embed doc chunks
|     Indexing Workers     |------------------------------+
| extract, chunk, coalesce |                              |
+-----------+--------------+                              v
            |                                     +------------------+
            |                                     | Embedding Service |
            |                                     +------------------+
            |
   (8) write indexes (bulk)
     (8a) Lexical Index (BM25/FTS)
     (8b) Vector Index (ANN)
            v
   +-------------------+            +-------------------+
   |   Vector Index    |            |  Lexical Index    |
   | (ANN per tenant)  |            | (BM25/FTS per tnt) |
   +-------------------+            +-------------------+

Query continuation:
(11) Search API -> embed query -> Vector Index (ANN) + Lexical Index (BM25)
(12) merge/rerank -> respond; emit audit; metrics/traces throughout


```
### Architecture Diagram — Ingestion + Indexing (Data Flow)

```text
Clients (UI/SDK)
   |
(1) POST /documents:init  (Idempotency-Key, metadata)
   v
+------------------------------+
| API Edge (WAF / Rate limit)  |
+--------------+---------------+
               |
               v 
+-----------------------------------------------+      (2a) append-only events
| Ingestion API Service                         |------------------------------->+--------------------------+
| AuthN + AuthZ/RBAC (tenant+role) + req_id     |                                | Audit Log (append-only) |
+-------+----------+----------------------------+                                +--------------------------+
        |          |
        | (2) check/write idempotency (durable)
        v          v
+----------------------+     (3) upsert metadata/status=INITIATED     +----------------------+
| Idempotency Store    |--------------------------------------------->| Metadata Store       |
| (tenant_id, idem_key)|                                              | (tenant-partitioned) |
+----------------------+                                              +----------------------+
        |
        | (4) return pre-signed URL + doc_id
        v
Client uploads file directly:
(5) PUT blob via pre-signed URL
   v
+------------------------------+
| Object Store (PDF/blob)      |
| (content-hash key, versioned)|
+------------------------------+

(6) POST /documents:finalize (doc_id, etag/checksum)
   v
+------------------------------+      (7) update metadata/status=STORED
| Ingestion API Service        |--------------------------------------------->+----------------------+
+--------------+---------------+                                              | Metadata Store       |
               |
               | (8) enqueue indexing job (outbox/txn for consistency)
               v
+------------------------------+
| Queue / Log (Kafka/SQS/etc.) |
+--------------+---------------+
               |
               | (9) consume job
               v
+------------------------------+      (10a) append-only events
| Indexing Workers             |------------------------------->+--------------------------+
| extract -> chunk -> coalesce |                                | Audit Log (append-only) |
+--------------+---------------+                                +--------------------------+
               |
               | (10) fetch blob (if needed)
               v
+------------------------------+
| Object Store                 |
+------------------------------+

(11) For each chunk/batch:
Indexing Workers -> Embedding Service -> (vectors returned)

+------------------------------+        (11a) embed(batch)         +------------------------+
| Indexing Workers             |---------------------------------->| Embedding Service      |
+--------------+---------------+                                   +------------------------+
               |
               | (12) write indexes (bulk)
               v
     +----------------------+            +----------------------+
     | Vector Index (ANN)   |            | Lexical Index (BM25) |
     | (per-tenant partition|            | (per-tenant partition|
     +----------------------+            +----------------------+

Observability: all services emit logs/metrics/traces; request_id propagates end-to-end.

```
**Client upload workflow**

1. Client calls `POST /documents:init` with metadata (title/tags/source) and an `Idempotency-Key` (or client-generated `doc_id`).
2. Ingestion Service:
   - AuthZ checks tenant + role.
   - Writes/looks up idempotency record `(tenant_id, idempotency_key)` → returns the same `doc_id` on retries.
   - Upserts metadata row as `status=INITIATED`.
   - Returns `doc_id` + pre-signed upload URL.
3. Client uploads the file directly to Object Store via the pre-signed URL (`PUT`). (Prefer content-hash object keys to dedupe identical payloads.)
4. Client calls `POST /documents:finalize` with `doc_id` (+ optional checksum/etag).
5. Ingestion Service:
   - Validates the object exists (and checksum/etag if provided).
   - Updates metadata `status=STORED`.
   - Enqueues indexing job via a transactional outbox (or equivalent) to avoid “metadata updated but no job”.
   - Emits audit event(s) for compliance.
   - Returns `202 Accepted` with `doc_id` and `status=STORED/QUEUED`.

Notes:
- Idempotency should apply to both `init` and `finalize`.
- Workers should also be idempotent (dedupe by `doc_id + content_version`).

### Architecture Diagram — Query / Retrieval (Data Flow)

```text
Clients (UI/SDK)
   |
(1) GET /search?q=...
   v
+------------------------------+
| API Edge (WAF / Rate limit)  |
+--------------+---------------+
               |
               v
+----------------------------------------------+
| Search API Service                            |
| AuthN + RBAC/AuthZ (tenant + role) + req_id   |
+-------------------+--------------------------+
                    |
                    | (2) cache lookup (tenant-scoped)
                    v
           +------------------------+
           | Cache (Redis/Memcache) |
           | - query->topK cache    |
           | - query_embedding cache|
           | - doc_meta cache       |
           +-----------+------------+
               hit?    |miss
                |      v
                |   (3) embed query (for semantic search)
                |      v
                |  +------------------------+
                |  | Embedding Service      |
                |  +-----------+------------+
                |              |
                |              | (4a) vector search (ANN)
                |              v
                |    +----------------------+
                |    | Vector Index (ANN)   |
                |    | (tenant partition)   |
                |    +----------+-----------+
                |               |
                |               | (4b) lexical search (BM25/FTS)
                |               v
                |    +----------------------+
                |    | Lexical Index (BM25) |
                |    | (tenant partition)   |
                |    +----------+-----------+
                |               |
                |               | (5) merge + rerank + paginate
                |               v
+---------------+------------------------------+
| Search API Service - continue                |
| (hybrid merge/rerank; enforce tenant filter) |
+---------------+------------------------------+
                |
                | (6) fetch metadata/snippets (maybe)
                v
      +------------------------------+
      | Metadata Store               |
      | (tenant-scoped queries only) |
      +---------------+--------------+
                      |
                      | (7) populate cache (tenant-scoped)
                      v
           +------------------------+
           | Cache                  |
           +------------------------+

(8) respond results (tenant-scoped)
   v
Clients

(9) Audit event (metadata only; avoid sensitive payloads)
Search API Service ---------------------------------------> +--------------------------+
                                                           | Audit Log (append-only)  |
                                                           +--------------------------+

Cache notes (keep it tenant-safe):
	•	Key by (tenant_id, normalized_query, filters, page); short TTL (e.g., 30–120s) for top-K results.
	•	Cache query embeddings by (tenant_id, normalized_query) with longer TTL.
	•	Cache document metadata/snippets by (tenant_id, doc_id) to reduce metadata-store reads.

```

---

## 2) Multi-Tenancy Strategy

### Authorization enforcement (Policy / Permission)
- Treat authorization as a **policy evaluation** step that produces `{tenant_id, actor_id, roles/scopes}` for each request.
- Implementation options:
  - **Embedded policy engine** in the API (fastest/lowest complexity) with policies sourced from a central store, or
  - A dedicated **Permission/Policy Service** for large orgs (centralized RBAC/ABAC, auditability, consistent decisions).
- Enforce “tenant-scoped” at multiple layers:
  - handler cannot override tenant_id
  - DAL requires tenant_id for every query
  - index retrieval requires tenant partition/filter

### Tenant identity
- Tenant context is derived from auth and propagated end-to-end:
  - `tenant_id`, `actor_id`, `roles`, `request_id`
- All operations are tenant-scoped; cross-tenant access is rejected.

### Isolation enforcement (“defense in depth”)
- **Edge**: per-tenant rate limits/quotas
- **Service layer**: auth middleware injects tenant; request handlers cannot override tenant_id
- **Data access layer**: queries require tenant_id parameter; shared libraries enforce it
- **Index layer**: tenant filtering is mandatory (partitioning or filter clause)

### Data partitioning choices
- **Default (recommended)**: shared infra + logical isolation
  - Metadata tables include `tenant_id` as required partition key
  - Index strategy:
    - **Hybrid**: index-per-tenant for large tenants; shared index + mandatory `tenant_id` filter for long tail
- **Stronger isolation (premium/regulatory)**:
  - DB-per-tenant or schema-per-tenant
  - Dedicated index cluster or dedicated index-per-tenant
  - Separate encryption keys / network segmentation

---

## 3) Scalability and Performance

### Ingestion: 100K docs/day
- **Asynchronous ingestion**:
  - Ingestion API does lightweight work (validate, metadata write, object-store write, enqueue)
  - Workers handle heavy tasks (extract/chunk/embed/index)
- **Backpressure**:
  - Edge rate limits (per tenant)
  - Queue buffers spikes; DLQ for poison messages
- **Idempotency & dedupe**:
  - Store `idempotency_key = hash(tenant_id, source_id, content_hash)`
  - If key exists and content unchanged → no-op or return existing `doc_id`

### Query: 10K concurrent queries
- Search API is stateless → horizontal scale
- **Hybrid retrieval** (default):
  - Vector ANN for semantic recall + lexical BM25 for precision
  - Merge results; optional lightweight rerank
- **Caching**:
  - **Query/result cache**: per-tenant normalized query+filters, short TTL
  - **Hot metadata cache**: doc status/details
  - Cache is not a replacement for the index; it reduces tail latency and protects downstreams

### Index update efficiency (avoid expensive re-index)
- **Coalesce updates**:
  - Version each doc (`doc_id + version/updated_at`)
  - Debounce within a short window; index only latest version
- **Bulk indexing**:
  - Micro-batch writes (N docs or T seconds)
  - Use backend bulk APIs to reduce shard churn
- **Batch rebuilds**:
  - Reserved for backfills/schema changes, not steady-state writes

---

## 4) Security and Compliance

### Authentication & Authorization
- AuthN: OAuth/JWT for users; API key for service-to-service
- AuthZ: tenant-scoped RBAC (admin / ingest / read / search)

### Encryption
- In transit: TLS everywhere
- At rest:
  - Object store encryption (KMS-equivalent)
  - DB encryption
  - Index encryption (if supported)
- Secrets: stored in a secrets manager; rotated

### Audit logging (compliance)
Goal: produce a **tamper-evident, append-only** record of security-relevant and compliance-relevant actions, queryable per tenant and exportable for audits.

**What to log (append-only events)**
- Document lifecycle: `init`, `upload_finalized`, `index_started`, `index_completed`, `update`, `delete`
- Search access: `search_performed` (log metadata only; do not log full query text if sensitive—store hashed/redacted form)
- Admin/security actions: API key changes, role changes, retention policy changes, quota overrides
- Auth events: authentication failures, authorization denials (403)

**Event fields (minimum)**
- `event_id`, `timestamp`, `tenant_id`, `actor_id`, `actor_type` (user/service)
- `action`, `resource_type`, `resource_id`, `request_id`, `ip/user_agent`
- `outcome` (success/fail) + `error_code`
- Optional: `checksum/etag`, `content_version`, `job_id`

**Storage + immutability**
- Write events to an append-only log store (e.g., WORM-capable object storage or an immutable log service).
- Use per-tenant retention policies (e.g., 90d/1y/7y) and enforce delete via policy, not ad-hoc.
- (Optional) Add tamper evidence: hash-chain events per tenant/day and store periodic digests.

**Access control**
- Audit logs are read-only to customers; only security/compliance roles can query/export.
- Separate encryption keys and strict IAM policies for audit log write/read paths.

**Performance**
- Audit writes are async where possible (queue/buffer) so ingest/search latency isn’t dominated by logging.

### Abuse prevention
- Request size limits + content type validation
- Per-tenant quotas and throttling
- Anomaly detection on query volume/patterns (future)

---

## 5) Technology Stack Justification + Tradeoffs

### Capability choices (cloud-agnostic)
- **Object Store** for raw docs: cheap, durable, large payloads
- **Metadata Store**:
  - RDBMS if relational queries/transactions matter
  - NoSQL if access is primarily key-based and needs high scale
- **Queue + DLQ**: decouple ingest from indexing; retries and failure isolation
- **Embedding Service**:
  - Hosted embedding API for speed
  - Self-hosted embeddings for compliance/cost/control
- **Search Index**:
  - **Single-engine hybrid** (text + vector in one system) → simplest ops + simpler merge logic
  - **Split engines** (dedicated vector DB + separate lexical) → best-in-class vector features, but more moving parts and operational surface
- **Cache**: Redis/Memcached for hot queries/results and metadata
- **Observability**: OpenTelemetry + centralized logs/metrics/traces

### Key tradeoffs
- Hosted embeddings: fastest delivery; vendor dependency; data governance needed
- Self-host embeddings: control/compliance; increased MLOps + ops complexity
- Single hybrid search engine: simpler architecture; may have fewer vector features than specialized DBs
- Split search engines: better specialization; requires merge/rerank logic and dual scaling

---

## 6) High Availability and Fault Tolerance

### General Ideas
- Stateless services deployed across multiple instances/zones
- Queue-based async pipeline with retries + DLQ
- Metadata store replicated; backups + restore procedures
- Index replicated; shard/replica strategy; rebuild/backfill support
- Timeouts + circuit breakers around embedding/index calls
- Degraded mode: lexical-only search if embedding service is unavailable
- Add multi-region DR and a replayable indexing pipeline for stronger HA/fault tolerance.

### Fault Tolerance for Ingestion/Indexing (idempotency & deduplication)

Because the ingestion → indexing pipeline is **at-least-once** (HTTP retries, queue redelivery, worker retries), every stage is designed to be **safe to repeat** and to produce **exactly-once effects**.

**Stable identity (dedupe key)**
- Use a single canonical dedupe key: **`(tenant_id, doc_id, content_version)`**.
- `doc_id` is stable per document (allocated in `documents:init`).
- `content_version` increments when a new upload replaces content for the same `doc_id`.

**Finalize is retry-safe (transactional outbox / equivalent)**
- `documents:finalize` performs a single transaction:
  - Update metadata to `STORED`
  - Insert an outbox row for indexing with a **unique constraint** on `(tenant_id, doc_id, content_version, event_type='INDEX')`
  - Emit audit event(s) (also idempotent via unique keys if needed)
- If finalize is retried, the unique constraint prevents duplicate job creation.

**Queue publishing is retry-safe**
- Publisher reads outbox and writes to the queue with message key = `tenant_id|doc_id` (ordering per doc).
- Message payload includes `tenant_id`, `doc_id`, `content_version`, and object location (e.g., `object_key`, optional `etag/checksum`).
- Producer retries are allowed; duplicates are tolerated because consumers dedupe on the canonical key.

**Workers are idempotent**
- Indexing workers maintain a durable `job_state` store keyed by the canonical dedupe key `(tenant_id, doc_id, content_version)`:
  - `RECEIVED → RUNNING → DONE` (and `FAILED` with retry count)
- On message receipt: if the key is already `DONE`, the worker **acks and skips**.

**Index writes are idempotent**
- Chunk IDs are deterministic: `chunk_id = hash(tenant_id, doc_id, content_version, chunk_index)`.
- Index writes use upserts (bulk indexing). Retrying the same bulk request converges to the same final state.
- Re-indexing on new `content_version` either:
  - keeps old versions but filters by latest version at query time, or
  - deletes old version chunks via `(tenant_id, doc_id, old_version)` (also retry-safe).

This design ensures that failures/retries (client, ingestion service, publisher, queue, workers, index cluster) do not cause corruption—at worst they cause bounded duplicate work, which is controlled by dedupe keys, unique constraints, and job state.

---

## 7) “With More Time”
- Tenant-level cost attribution + chargeback (index/storage/compute)
- Per-tenant encryption keys + rotation
- Advanced reranking (cross-encoder) + learning-to-rank. Reranking happens in the query path. 
- Multi-region DR and replayable indexing pipeline
