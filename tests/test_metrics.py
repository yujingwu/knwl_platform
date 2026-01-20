def test_metrics_reflect_requests_and_errors(client):
    client.get("/api/v1/health")
    client.post(
        "/api/v1/tenants/t1/documents",
        headers={"X-API-Key": "key_t1"},
        json={"title": "Doc", "content": "Content", "tags": ["a"]},
    )
    client.post(
        "/api/v1/tenants/t1/documents",
        json={"title": "Doc", "content": "Content", "tags": ["a"]},
    )
    response = client.get("/api/v1/metrics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["requests"]["total"] >= 3
    assert payload["errors"]["total"] >= 1
    assert "400" in payload["errors"]["byStatus"] or "401" in payload["errors"]["byStatus"]


def test_metrics_skip_none_tenant_bucket(client):
    client.get("/api/v1/health")
    response = client.get("/api/v1/metrics")
    assert response.status_code == 200
    payload = response.json()
    by_tenant = payload["requests"]["byTenant"]
    assert "null" not in by_tenant
    assert "None" not in by_tenant
    assert None not in by_tenant
    assert "GET /api/v1/health" in payload["requests"]["byEndpoint"]

