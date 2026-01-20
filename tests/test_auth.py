def test_missing_api_key_returns_401(client):
    response = client.post(
        "/api/v1/tenants/t1/documents",
        json={"title": "Doc", "content": "Content", "tags": ["a"]},
    )
    assert response.status_code == 401


def test_invalid_api_key_returns_401(client):
    response = client.post(
        "/api/v1/tenants/t1/documents",
        headers={"X-API-Key": "bad_key"},
        json={"title": "Doc", "content": "Content", "tags": ["a"]},
    )
    assert response.status_code == 401


def test_tenant_not_authorized_returns_403(client):
    response = client.post(
        "/api/v1/tenants/t2/documents",
        headers={"X-API-Key": "key_t1"},
        json={"title": "Doc", "content": "Content", "tags": ["a"]},
    )
    assert response.status_code == 403

