from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.auth import require_tenant
from app.db import repo
from app.models.schemas import DocumentIn, IngestResponse

router = APIRouter(prefix="/api/v1/tenants/{tenantId}/documents", tags=["documents"])


def _validate_document(doc: DocumentIn, request: Request) -> None:
    settings = request.app.state.settings
    if len(doc.title) > settings.max_title_len:
        raise HTTPException(status_code=400, detail="Title too long")
    if len(doc.content) > settings.max_content_len:
        raise HTTPException(status_code=400, detail="Content too long")
    if len(doc.tags) > settings.max_tags:
        raise HTTPException(status_code=400, detail="Too many tags")


@router.post("", status_code=status.HTTP_201_CREATED, response_model=IngestResponse)
def ingest_document(
    tenantId: str = Depends(require_tenant),
    payload: DocumentIn,
    request: Request,
) -> IngestResponse:
    _validate_document(payload, request)
    conn = request.app.state.db
    lock = request.app.state.db_lock
    document_id, created_at = repo.insert_document(
        conn,
        lock,
        tenantId,
        payload.title,
        payload.content,
        payload.tags,
    )
    return IngestResponse(
        documentId=document_id,
        tenantId=tenantId,
        createdAt=created_at,
    )

