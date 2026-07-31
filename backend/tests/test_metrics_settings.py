from models.order import Order, OrderItem
from models.settings import StoreSetting


def make_paid_order(db_session, user, product, quantity=1):
    order = Order(user_id=user.id, status="paid", total_amount=product.price * quantity, payment_method="anticipado")
    db_session.add(order)
    db_session.flush()
    db_session.add(OrderItem(order_id=order.id, product_id=product.id, quantity=quantity, unit_price=product.price))
    db_session.commit()
    return order


# ── /metrics/dashboard ───────────────────────────────────────────────────────

def test_dashboard_requires_admin(client, auth_headers):
    resp = client.get("/metrics/dashboard", headers=auth_headers)
    assert resp.status_code == 403


def test_dashboard_requires_token(client):
    resp = client.get("/metrics/dashboard")
    assert resp.status_code in (401, 403)


def test_dashboard_returns_expected_shape(client, admin_headers, db_session, normal_user, sample_product):
    make_paid_order(db_session, normal_user, sample_product, quantity=2)

    resp = client.get("/metrics/dashboard", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    for key in ("ventas", "ordenes", "usuarios", "productos", "carritos", "top_productos", "ventas_por_dia", "ordenes_recientes"):
        assert key in body

    assert body["ventas"]["total_historico"] == sample_product.price * 2
    assert body["ordenes"]["total"] == 1
    assert len(body["top_productos"]) == 1
    assert body["top_productos"][0]["total_vendido"] == 2


# ── /settings/ ───────────────────────────────────────────────────────────────

def test_get_settings_returns_defaults(client):
    resp = client.get("/settings/")
    assert resp.status_code == 200
    assert resp.json()["store_name"] == "Velonox"


def test_update_settings_requires_admin(client, auth_headers):
    resp = client.put("/settings/", json={"store_name": "Otra Tienda"}, headers=auth_headers)
    assert resp.status_code == 403


def test_update_settings_as_admin(client, admin_headers):
    resp = client.put("/settings/", json={"store_name": "Velonox Actualizado"}, headers=admin_headers)
    assert resp.status_code == 200

    settings = client.get("/settings/").json()
    assert settings["store_name"] == "Velonox Actualizado"


def test_update_settings_overwrites_existing_key(client, admin_headers):
    client.put("/settings/", json={"store_name": "Primero"}, headers=admin_headers)
    client.put("/settings/", json={"store_name": "Segundo"}, headers=admin_headers)

    settings = client.get("/settings/").json()
    assert settings["store_name"] == "Segundo"


# ── /settings/trm ────────────────────────────────────────────────────────────

def test_trm_manual_mode(client, db_session):
    db_session.add(StoreSetting(key="trm_auto", value="false"))
    db_session.add(StoreSetting(key="trm_usd_cop", value="4500"))
    db_session.commit()

    resp = client.get("/settings/trm")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "manual"
    assert body["trm"] == 4500.0


def test_trm_auto_mode_falls_back_to_manual_on_network_failure(client, db_session, monkeypatch):
    db_session.add(StoreSetting(key="trm_auto", value="true"))
    db_session.add(StoreSetting(key="trm_usd_cop", value="4300"))
    db_session.commit()

    class _FailingAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **k):
            raise RuntimeError("sin red en tests")

    monkeypatch.setattr("routes.settings.httpx.AsyncClient", _FailingAsyncClient)

    resp = client.get("/settings/trm")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "manual"
    assert body["trm"] == 4300.0


def test_trm_auto_mode_success(client, db_session, monkeypatch):
    db_session.add(StoreSetting(key="trm_auto", value="true"))
    db_session.commit()

    class _FakeResponse:
        def json(self):
            return {"rates": {"COP": 4321.0}}

    class _SuccessAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **k):
            return _FakeResponse()

    monkeypatch.setattr("routes.settings.httpx.AsyncClient", _SuccessAsyncClient)

    resp = client.get("/settings/trm")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "auto"
    assert body["trm"] == 4321.0


def test_update_trm_requires_admin(client, auth_headers):
    resp = client.put("/settings/trm", json={"trm": 4000}, headers=auth_headers)
    assert resp.status_code == 403


def test_update_trm_as_admin(client, admin_headers, db_session):
    resp = client.put("/settings/trm", json={"trm": 4700, "auto": False}, headers=admin_headers)
    assert resp.status_code == 200

    trm_resp = client.get("/settings/trm").json()
    assert trm_resp["trm"] == 4700.0
    assert trm_resp["source"] == "manual"


def test_update_trm_overwrites_existing_values(client, admin_headers):
    client.put("/settings/trm", json={"trm": 4000, "auto": True}, headers=admin_headers)
    client.put("/settings/trm", json={"trm": 4800, "auto": False}, headers=admin_headers)

    trm_resp = client.get("/settings/trm").json()
    assert trm_resp["trm"] == 4800.0
    assert trm_resp["source"] == "manual"
