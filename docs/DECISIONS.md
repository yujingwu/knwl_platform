# Step 2 DECISIONS

This file captures deliberate implementation choices for the Part 2 simplified service. Update this file if behavior changes or if you deviate from `docs/SPEC.md` / `docs/API.md`.

## Decisions (current)
1) **Language/Framework**: Python + FastAPI + Pydantic  
   - Rationale: low boilerplate, auto OpenAPI/Swagger, fast iteration.

2) **Storage**: SQLite file DB (embedded)  
   - Rationale: explicitly allowed; easiest local setup.

3) **Search/Indexing**: SQLite FTS5 with external content table + triggers  
   - Rationale: fast text search, built-in ranking/snippets, minimal dependencies.

4) **Auth**: API key middleware (`X-API-Key`) with tenant allow-list (`API_KEYS_JSON`)  
   - Rationale: simplest tenant authorization model that meets requirement.

5) **Metrics format**: JSON (not Prometheus text format)  
   - Rationale: simplest to implement and validate; still provides required fields.

6) **Benchmark approach**: Python script `scripts/benchmark.py`  
   - Rationale: demonstrates p95 < 100ms @ 10K docs; repeatable.

7) **Health/Metrics auth**: unauthenticated  
   - Rationale: operational simplicity; can be tightened later.

## Known tradeoffs
- SQLite is not suitable for multi-instance shared persistence; acceptable for Part 2 simplified service.
- `limit/offset` pagination is simple; cursor-based paging is better for deep pagination but unnecessary at 10K docs.
