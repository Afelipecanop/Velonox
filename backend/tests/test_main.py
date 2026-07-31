def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
