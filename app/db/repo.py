import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, List, Tuple


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def insert_document(
    conn,
    lock: threading.Lock,
    tenant_id: str,
    title: str,
    content: str,
    tags: List[str],
) -> Tuple[str, str]:
    document_id = str(uuid.uuid4())
    created_at = _now_iso()
    tags_json = json.dumps(tags)
    with lock:
        conn.execute(
            """
            INSERT INTO documents (tenant_id, document_id, title, content, tags, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (tenant_id, document_id, title, content, tags_json, created_at, created_at),
        )
        conn.commit()
    return document_id, created_at


def search_documents(
    conn,
    lock: threading.Lock,
    tenant_id: str,
    query: str,
    limit: int,
    offset: int,
) -> List[dict[str, Any]]:
    with lock:
        rows = conn.execute(
            """
            SELECT d.document_id,
                   d.title,
                   d.tags,
                   d.created_at,
                   snippet(documents_fts, 2, '<b>', '</b>', '...', 10) AS snippet,
                   bm25(documents_fts) AS score_raw
            FROM documents_fts
            JOIN documents d ON d.rowid = documents_fts.rowid
            WHERE documents_fts.tenant_id = ?
              AND documents_fts MATCH ?
            ORDER BY score_raw
            LIMIT ? OFFSET ?;
            """,
            (tenant_id, query, limit, offset),
        ).fetchall()
    results: List[dict[str, Any]] = []
    for row in rows:
        score_raw = float(row["score_raw"])
        score = 1.0 / (1.0 + score_raw)
        results.append(
            {
                "documentId": row["document_id"],
                "title": row["title"],
                "tags": json.loads(row["tags"]),
                "createdAt": row["created_at"],
                "snippet": row["snippet"],
                "score": score,
            }
        )
    results.sort(key=lambda item: item["score"], reverse=True)
    return results


def count_documents(
    conn,
    lock: threading.Lock,
    tenant_id: str,
    query: str,
) -> int:
    with lock:
        row = conn.execute(
            """
            SELECT COUNT(*)
            FROM documents_fts
            WHERE tenant_id = ?
              AND documents_fts MATCH ?;
            """,
            (tenant_id, query),
        ).fetchone()
    return int(row[0]) if row else 0


def document_counts_by_tenant(conn, lock: threading.Lock) -> dict[str, int]:
    with lock:
        rows = conn.execute(
            """
            SELECT tenant_id, COUNT(*)
            FROM documents
            GROUP BY tenant_id;
            """
        ).fetchall()
    return {row["tenant_id"]: int(row[1]) for row in rows}

