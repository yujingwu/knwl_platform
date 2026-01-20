from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_tenant(
    request: Request,
    tenantId: str,
    api_key: str | None = Depends(API_KEY_HEADER),
) -> str:
    settings = request.app.state.settings
    if not api_key or api_key not in settings.api_keys:
        raise HTTPException(status_code=401, detail="Invalid API key")
    if tenantId not in settings.api_keys[api_key]:
        raise HTTPException(status_code=403, detail="Tenant not authorized")
    return tenantId

