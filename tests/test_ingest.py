def test_invalid_body_returns_400(client):
    response = client.post(
        "/api/v1/tenants/t1/documents",
        headers={"X-API-Key": "key_t1"},
        json={"title": "", "content": "Content", "tags": ["a"]},
    )
    assert response.status_code == 400


def test_ingest_returns_document_id(client):
    response = client.post(
        "/api/v1/tenants/t1/documents",
        headers={"X-API-Key": "key_t1"},
        json={"title": "Doc", "content": "Content", "tags": ["tag1"]},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["tenantId"] == "t1"
    assert "documentId" in payload
    assert "createdAt" in payload

