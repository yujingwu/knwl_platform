def _ingest(client, tenant_id, api_key, title, content, tags):
    return client.post(
        f"/api/v1/tenants/{tenant_id}/documents",
        headers={"X-API-Key": api_key},
        json={"title": title, "content": content, "tags": tags},
    )


def test_ingest_then_search_returns_doc(client):
    _ingest(client, "t1", "key_t1", "Doc One", "Hello world", ["hello"])
    response = client.get(
        "/api/v1/tenants/t1/documents/search",
        headers={"X-API-Key": "key_t1"},
        params={"q": "Hello"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    assert any(item["title"] == "Doc One" for item in payload["results"])


def test_search_is_tenant_scoped(client):
    _ingest(client, "t1", "key_t1", "Doc A", "Tenant A content", ["a"])
    _ingest(client, "t2", "key_t2", "Doc B", "Tenant B content", ["b"])
    response = client.get(
        "/api/v1/tenants/t1/documents/search",
        headers={"X-API-Key": "key_t1"},
        params={"q": "Tenant"},
    )
    assert response.status_code == 200
    titles = {item["title"] for item in response.json()["results"]}
    assert "Doc A" in titles
    assert "Doc B" not in titles


def test_search_results_sorted_by_score_desc(client):
    _ingest(client, "t1", "key_t1", "Doc One", "alpha beta", ["a"])
    _ingest(client, "t1", "key_t1", "Doc Two", "alpha alpha beta", ["b"])
    response = client.get(
        "/api/v1/tenants/t1/documents/search",
        headers={"X-API-Key": "key_t1"},
        params={"q": "alpha"},
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) >= 2
    assert results[0]["score"] >= results[1]["score"]

