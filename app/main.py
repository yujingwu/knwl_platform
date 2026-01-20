import os
import threading
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api import routes_docs, routes_health, routes_metrics, routes_search
from app.core.config import get_settings
from app.core.logging import log_request, setup_logging
from app.core.metrics import MetricsCollector
from app.db.schema import apply_schema
from app.db.sqlite import get_connection


def _get_endpoint_label(request: Request) -> str:
    route = request.scope.get("route")
    if route and hasattr(route, "path"):
        return f"{request.method} {route.path}"
    return f"{request.method} {request.url.path}"


def _get_tenant_id(request: Request) -> Optional[str]:
    return request.path_params.get("tenantId") if request.path_params else None


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        app.state.db.close()

    app = FastAPI(lifespan=lifespan)
    conn = get_connection(settings.db_path)
    apply_schema(conn)

    app.state.db = conn
    app.state.db_lock = threading.Lock()
    app.state.settings = settings
    app.state.metrics = MetricsCollector()

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=400, content={"detail": "Invalid request"})

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            response = JSONResponse(
                status_code=500, content={"detail": "Internal Server Error"}
            )
        latency_ms = (time.perf_counter() - start) * 1000
        endpoint_label = _get_endpoint_label(request)
        tenant_id = _get_tenant_id(request)
        app.state.metrics.record_request(endpoint_label, tenant_id, status_code, latency_ms)
        log_request(
            {
                "request_id": request_id,
                "tenant_id": tenant_id,
                "method": request.method,
                "path": request.url.path,
                "status": status_code,
                "latency_ms": latency_ms,
            }
        )
        response.headers["X-Request-Id"] = request_id
        return response

    app.include_router(routes_docs.router)
    app.include_router(routes_search.router)
    app.include_router(routes_health.router)
    app.include_router(routes_metrics.router)

    return app


if os.getenv("APP_DISABLE_AUTOCREATE") == "1":
    app = FastAPI()
else:
    app = create_app()

