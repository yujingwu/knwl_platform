from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.auth import require_tenant
from app.db import repo
from app.models.schemas import SearchResponse

router = APIRouter(
    prefix="/api/v1/tenants/{tenantId}/documents/search", tags=["search"]
)

@router.get("", response_model=SearchResponse)
def search_documents(
    request: Request,
    q: str = Query(..., alias="q"),
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    tenantId: str = Depends(require_tenant),
) -> SearchResponse:
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query cannot be blank")
    conn = request.app.state.db
    lock = request.app.state.db_lock
    results = repo.search_documents(conn, lock, tenantId, q, limit, offset)
    total = repo.count_documents(conn, lock, tenantId, q)
    return SearchResponse(
        tenantId=tenantId,
        query=q,
        limit=limit,
        offset=offset,
        total=total,
        results=results,
    )

