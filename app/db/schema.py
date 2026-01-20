SCHEMA_SQL = """
-- Base table
CREATE TABLE IF NOT EXISTS documents (
  tenant_id   TEXT NOT NULL,
  document_id TEXT NOT NULL,
  title       TEXT NOT NULL,
  content     TEXT NOT NULL,
  tags        TEXT NOT NULL, -- JSON array string
  created_at  TEXT NOT NULL, -- ISO8601
  updated_at  TEXT NOT NULL, -- ISO8601
  PRIMARY KEY (tenant_id, document_id)
);

CREATE INDEX IF NOT EXISTS idx_documents_tenant_created
ON documents(tenant_id, created_at DESC);

-- External-content FTS5 table (links to documents via rowid)
CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
  tenant_id UNINDEXED,
  title,
  content,
  tags,
  content='documents',
  content_rowid='rowid'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
  INSERT INTO documents_fts(rowid, tenant_id, title, content, tags)
  VALUES (new.rowid, new.tenant_id, new.title, new.content, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
  INSERT INTO documents_fts(documents_fts, rowid, tenant_id, title, content, tags)
  VALUES('delete', old.rowid, old.tenant_id, old.title, old.content, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
  INSERT INTO documents_fts(documents_fts, rowid, tenant_id, title, content, tags)
  VALUES('delete', old.rowid, old.tenant_id, old.title, old.content, old.tags);
  INSERT INTO documents_fts(rowid, tenant_id, title, content, tags)
  VALUES (new.rowid, new.tenant_id, new.title, new.content, new.tags);
END;
"""


def apply_schema(conn) -> None:
    conn.executescript(SCHEMA_SQL)

