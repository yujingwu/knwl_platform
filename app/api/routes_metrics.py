from fastapi import APIRouter, Request

from app.db import repo
from app.models.schemas import MetricsResponse

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])


@router.get("", response_model=MetricsResponse)
def metrics(request: Request) -> MetricsResponse:
    metrics_collector = request.app.state.metrics
    conn = request.app.state.db
    lock = request.app.state.db_lock
    snapshot = metrics_collector.snapshot()
    snapshot["documents"] = {"byTenant": repo.document_counts_by_tenant(conn, lock)}
    return MetricsResponse(**snapshot)

