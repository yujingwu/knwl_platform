from typing import List

from pydantic import BaseModel, Field


class DocumentIn(BaseModel):
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    tags: List[str]


class IngestResponse(BaseModel):
    documentId: str
    tenantId: str
    createdAt: str


class SearchResult(BaseModel):
    documentId: str
    title: str
    snippet: str
    tags: List[str]
    score: float
    createdAt: str


class SearchResponse(BaseModel):
    tenantId: str
    query: str
    limit: int
    offset: int
    total: int
    results: List[SearchResult]


class HealthResponse(BaseModel):
    status: str
    time: str


class MetricsResponse(BaseModel):
    uptimeSeconds: int
    requests: dict
    latencyMs: dict
    errors: dict
    documents: dict

