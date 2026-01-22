# Simplified Knowledge Indexing Service (Part 2)

## Project structure (by part)
- Part 1 (Scalable System Design): Part1_KnwlPft_scalable_Design_doc.md
- Part 2 (Core Implementation): app/, tests/, scripts/, docs/
- Part 3 (Infrastructure as Code): infra/terraform/ + infra/README_IAC.md
- Part 3 (Containerization artifact): Dockerfile + .dockerignore (builds the Part 2 service image)

## Execution status for Part 2 (what I actually ran)
I was able to successfully 
- set up local environment
- start the server
- test 4 endpoints using curl and Swagger UI
- finish all coverage and benchmark tests
- verify OPENAPI JSON works


## Local setup
1) Create and activate a virtualenv
   - `python3 -m venv knwl_pf`
   - `source knwl_pf/bin/activate`
2) Install dependencies
   - `pip install -r requirements.txt`
3) Set `API_KEYS_JSON`
   - Example: `export API_KEYS_JSON='{"key_admin":["t1","t2"],"key_t1":["t1"]}'`
4) Initialize/create the SQLite DB
   - The app creates the DB file on startup at `DB_PATH` (default `./data/app.db`)
5) Run the server
   - `uvicorn app.main:app --reload --port 8000`
6) API docs
   - Swagger UI: `http://localhost:8000/docs`
   - OpenAPI JSON: `http://localhost:8000/openapi.json`

## Example usage (curl)
### Ingest a document
```
curl -X POST "http://localhost:8000/api/v1/tenants/t1/documents" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: key_t1" \
  -d '{"title":"Doc title","content":"Plain text content","tags":["tag1","tag2"]}'
```

### Search documents
```
curl "http://localhost:8000/api/v1/tenants/t1/documents/search?q=content&limit=10&offset=0" \
  -H "X-API-Key: key_t1"
```

### Health endpoint
```
curl "http://localhost:8000/api/v1/health"
```

### Metrics endpoint
```
curl "http://localhost:8000/api/v1/metrics"
```

## Testing
- Run tests: `pytest`
  - Note: this repo includes pytest.ini to ensure the repo root is on PYTHONPATH so app/ imports work consistently across environments.
- Run coverage: `pytest --cov=app --cov-report=term-missing`
  - Ensure coverage > 70%

## Benchmark
- Run from repo root: `python -m scripts.benchmark.py --queries 500 --threshold-ms 100`
  - Uses in-process `TestClient` against the FastAPI app.
  - Output: prints p50/p95 latencies in ms; exits non-zero if p95 exceeds threshold.
- Alternative if your environment has import path issues: `PYTHONPATH=. python scripts/benchmark.py --queries 500 --threshold-ms 100`

