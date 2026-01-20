import argparse
import os
import random
import statistics
import time

from fastapi.testclient import TestClient

from app.core import config
from app.db import repo
from app.main import create_app


def _random_text(words, count):
    return " ".join(random.choice(words) for _ in range(count))


def _ensure_api_keys(api_key: str, tenant_id: str) -> None:
    if os.getenv("API_KEYS_JSON"):
        return
    os.environ["API_KEYS_JSON"] = f'{{"{api_key}":["{tenant_id}"]}}'


def main() -> None:
    parser = argparse.ArgumentParser(description="Search benchmark")
    parser.add_argument("--tenant", default="t1")
    parser.add_argument("--api-key", default="benchmark_key")
    parser.add_argument("--docs", type=int, default=10000)
    parser.add_argument("--queries", type=int, default=500)
    parser.add_argument("--threshold-ms", type=float, default=100.0)
    args = parser.parse_args()

    _ensure_api_keys(args.api_key, args.tenant)
    if not os.getenv("DB_PATH"):
        os.environ["DB_PATH"] = "./data/benchmark.db"

    config.get_settings.cache_clear()
    app = create_app()
    client = TestClient(app)

    words = ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "theta"]
    conn = app.state.db
    lock = app.state.db_lock

    for idx in range(args.docs):
        title = f"Doc {idx}"
        content = _random_text(words, 20)
        tags = [random.choice(words)]
        repo.insert_document(conn, lock, args.tenant, title, content, tags)

    for _ in range(20):
        client.get(
            f"/api/v1/tenants/{args.tenant}/documents/search",
            headers={"X-API-Key": args.api_key},
            params={"q": random.choice(words)},
        )

    latencies = []
    for _ in range(args.queries):
        query = random.choice(words)
        start = time.perf_counter()
        response = client.get(
            f"/api/v1/tenants/{args.tenant}/documents/search",
            headers={"X-API-Key": args.api_key},
            params={"q": query},
        )
        if response.status_code != 200:
            raise SystemExit(f"Unexpected status: {response.status_code}")
        latencies.append((time.perf_counter() - start) * 1000)

    p50 = statistics.median(latencies)
    p95 = statistics.quantiles(latencies, n=100)[94]
    print(f"p50={p50:.2f}ms p95={p95:.2f}ms")
    if p95 > args.threshold_ms:
        raise SystemExit(f"p95 {p95:.2f}ms exceeded threshold {args.threshold_ms}ms")


if __name__ == "__main__":
    main()

