import json

import requests


class _FakeAnthropicResponse:
    def __init__(self, text):
        self._text = text

    def json(self):
        return {"content": [{"text": self._text}]}


def make_fake_async_client(response_text=None, raise_exc=None):
    """Factory for a class that stands in for httpx.AsyncClient - routes/layout.py's
    /generate-block does `async with httpx.AsyncClient() as client:` with no
    constructor args, so this must be a zero-arg-constructible class, not an instance."""
    class _FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            if raise_exc:
                raise raise_exc
            return _FakeAnthropicResponse(response_text)

    return _FakeAsyncClient


def fake_requests_post(response_text=None, status_code=200, raise_exc=None):
    def _post(*a, **k):
        if raise_exc:
            raise raise_exc

        class _Resp:
            def __init__(self):
                self.status_code = status_code

            def json(self):
                return {"content": [{"text": response_text}]}
        return _Resp()
    return _post


# ── /layout/generate-block ───────────────────────────────────────────────────

def test_generate_block_requires_admin(client, auth_headers):
    resp = client.post("/layout/generate-block", json={"prompt": "una seccion de testimonios"}, headers=auth_headers)
    assert resp.status_code == 403


def test_generate_block_requires_token(client):
    resp = client.post("/layout/generate-block", json={"prompt": "x"})
    assert resp.status_code in (401, 403)


def test_generate_block_success(client, admin_headers, monkeypatch):
    payload = json.dumps({"html": "<section>Hola</section>", "css": ".x{color:red}"})
    monkeypatch.setattr("routes.layout.httpx.AsyncClient", make_fake_async_client(payload))

    resp = client.post("/layout/generate-block", json={"prompt": "una seccion de bienvenida"}, headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["html"] == "<section>Hola</section>"
    assert body["css"] == ".x{color:red}"


def test_generate_block_strips_markdown_fences(client, admin_headers, monkeypatch):
    raw = "```json\n" + json.dumps({"html": "<p>ok</p>", "css": ""}) + "\n```"
    monkeypatch.setattr("routes.layout.httpx.AsyncClient", make_fake_async_client(raw))

    resp = client.post("/layout/generate-block", json={"prompt": "algo"}, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["html"] == "<p>ok</p>"


def test_generate_block_non_json_response_falls_back_to_raw_text(client, admin_headers, monkeypatch):
    monkeypatch.setattr("routes.layout.httpx.AsyncClient", make_fake_async_client("esto no es json"))

    resp = client.post("/layout/generate-block", json={"prompt": "algo"}, headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["html"] == "esto no es json"
    assert body["css"] == ""


def test_generate_block_missing_api_key(client, admin_headers, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    resp = client.post("/layout/generate-block", json={"prompt": "algo"}, headers=admin_headers)
    assert resp.status_code == 500


def test_generate_block_missing_prompt_still_calls_ai(client, admin_headers, monkeypatch):
    # /generate-block has no pydantic validation on "prompt" (raw dict body) -
    # an absent prompt just defaults to "" and still hits the (mocked) API.
    monkeypatch.setattr(
        "routes.layout.httpx.AsyncClient",
        make_fake_async_client(json.dumps({"html": "<p>vacio</p>", "css": ""})),
    )
    resp = client.post("/layout/generate-block", json={}, headers=admin_headers)
    assert resp.status_code == 200


# ── /layout/ai-generate ──────────────────────────────────────────────────────

def test_ai_generate_requires_admin(client, auth_headers):
    resp = client.post("/layout/ai-generate", json={"prompt": "una seccion de testimonios"}, headers=auth_headers)
    assert resp.status_code == 403


def test_ai_generate_requires_token(client):
    resp = client.post("/layout/ai-generate", json={"prompt": "x"})
    assert resp.status_code in (401, 403)


def test_ai_generate_success(client, admin_headers, monkeypatch):
    payload = json.dumps({"html": "<section>Hola</section>", "css": ".y{color:blue}"})
    monkeypatch.setattr("routes.layout.http_requests.post", fake_requests_post(payload))

    resp = client.post("/layout/ai-generate", json={"prompt": "una seccion de bienvenida"}, headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["html"] == "<section>Hola</section>"
    assert body["css"] == ".y{color:blue}"


def test_ai_generate_malformed_json_falls_back_to_raw_text(client, admin_headers, monkeypatch):
    monkeypatch.setattr("routes.layout.http_requests.post", fake_requests_post("texto plano, no json"))

    resp = client.post("/layout/ai-generate", json={"prompt": "algo"}, headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["html"] == "texto plano, no json"
    assert body["css"] == ""


def test_ai_generate_missing_api_key(client, admin_headers, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    resp = client.post("/layout/ai-generate", json={"prompt": "algo"}, headers=admin_headers)
    assert resp.status_code == 503


def test_ai_generate_timeout(client, admin_headers, monkeypatch):
    monkeypatch.setattr(
        "routes.layout.http_requests.post",
        fake_requests_post(raise_exc=requests.exceptions.Timeout()),
    )
    resp = client.post("/layout/ai-generate", json={"prompt": "algo"}, headers=admin_headers)
    assert resp.status_code == 504


def test_ai_generate_request_exception(client, admin_headers, monkeypatch):
    monkeypatch.setattr(
        "routes.layout.http_requests.post",
        fake_requests_post(raise_exc=requests.exceptions.ConnectionError()),
    )
    resp = client.post("/layout/ai-generate", json={"prompt": "algo"}, headers=admin_headers)
    assert resp.status_code == 502


def test_ai_generate_non_200_from_anthropic(client, admin_headers, monkeypatch):
    monkeypatch.setattr(
        "routes.layout.http_requests.post",
        fake_requests_post(response_text="", status_code=500),
    )
    resp = client.post("/layout/ai-generate", json={"prompt": "algo"}, headers=admin_headers)
    assert resp.status_code == 502


def test_ai_generate_empty_prompt_rejected(client, admin_headers):
    resp = client.post("/layout/ai-generate", json={"prompt": "   "}, headers=admin_headers)
    assert resp.status_code == 422


def test_ai_generate_prompt_too_long_rejected(client, admin_headers):
    resp = client.post("/layout/ai-generate", json={"prompt": "x" * 1001}, headers=admin_headers)
    assert resp.status_code == 422


def test_ai_generate_missing_prompt_field_rejected(client, admin_headers):
    resp = client.post("/layout/ai-generate", json={}, headers=admin_headers)
    assert resp.status_code == 422
