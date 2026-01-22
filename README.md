# Simplified Knowledge Indexing Service (Part 2)

## Project structure (by part)
- Part 1 (Scalable System Design): Part1_KnwlPft_scalable_Design_doc.md
- Part 2 (Core Implementation): app/, tests/, scripts/, docs/
- Part 3 (Infrastructure as Code): infra/terraform/ + infra/README_IAC.md 
- Part 3 (Containerization artifact): Dockerfile + .dockerignore (optional local container run; required for ECS)

## Execution status for Part 2 (what I actually ran)
I was able to successfully 
- set up the local environment
- start the server
- test 4 endpoints using curl and Swagger UI
- finish all coverage and benchmark tests
- verify OPENAPI JSON works
- set up the container and run the server in the container


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

## Containerization (Docker) — optional locally, required for ECS

This repo includes a `Dockerfile` and `.dockerignore` at the repo root to build the Part 2 FastAPI service image (used by Part 3 ECS). The container runs the same service as local dev; by default it uses SQLite via `DB_PATH`.

### When you should use Docker
- To validate the service runs as a container (closer to the ECS deployment model).
- To demonstrate a production-style packaging artifact for Part 3.

### When you do NOT need Docker
- If you are running locally for development/testing using the venv instructions below.  
  The non-Docker path is the primary local dev workflow for this take-home.

### Quick local Docker sanity check
```bash
docker build -t knwl-platform:local .
docker run --rm -p 8000:8000 \
  -e API_KEYS_JSON='{"key_admin":["t1","t2"],"key_t1":["t1"]}' \
  knwl-platform:local
```
Then verify:
- Health: `http://localhost:8000/api/v1/health`
- Swagger UI: `http://localhost:8000/docs`

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
- Run from repo root: `python -m scripts.benchmark --queries 500 --threshold-ms 100`
  - Uses in-process `TestClient` against the FastAPI app.
  - Output: prints p50/p95 latencies in ms; exits non-zero if p95 exceeds threshold.
- Alternative if your environment has import path issues: `PYTHONPATH=. python scripts/benchmark.py --queries 500 --threshold-ms 100`

