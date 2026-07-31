import base64
import hashlib
import hmac
import json
import os

from models.order import Order
from models.product import Product
from models.cart import Cart, CartItem


def add_to_cart(db_session, user, product, quantity):
    cart = db_session.query(Cart).filter(Cart.user_id == user.id).first()
    item = CartItem(cart_id=cart.id, product_id=product.id, quantity=quantity)
    db_session.add(item)
    db_session.commit()
    return item


def send_bold_webhook(client, payload, *, bad_signature=False):
    raw_body = json.dumps(payload).encode()
    if bad_signature:
        signature = "firma-invalida"
    else:
        secret = os.environ["BOLD_SECRET_KEY"]
        encoded = base64.b64encode(raw_body)
        signature = hmac.new(secret.encode(), encoded, hashlib.sha256).hexdigest()
    return client.post(
        "/payments/bold/webhook",
        content=raw_body,
        headers={"x-bold-signature": signature, "Content-Type": "application/json"},
    )


def bold_approved_payload(bold_order_id):
    return {"type": "SALE_APPROVED", "data": {"metadata": {"reference": bold_order_id}, "bold_code": "B001"}}


def bold_rejected_payload(bold_order_id):
    return {"type": "SALE_REJECTED", "data": {"metadata": {"reference": bold_order_id}, "bold_code": "B010"}}


CHECKOUT_BODY = {
    "customer_phone": "3001234567",
    "document_type": "CC",
    "document_number": "123456789",
    "shipping_address": "Calle 1 # 2-3",
    "department_name": "Cundinamarca",
    "city_name": "Bogota",
}


# ── /payments/checkout ───────────────────────────────────────────────────────

def test_checkout_requires_token(client):
    resp = client.post("/payments/checkout", json={**CHECKOUT_BODY, "payment_method": "anticipado"})
    assert resp.status_code in (401, 403)


def test_checkout_empty_cart(client, auth_headers):
    resp = client.post("/payments/checkout", json={**CHECKOUT_BODY, "payment_method": "anticipado"}, headers=auth_headers)
    assert resp.status_code == 400
    assert "vacío" in resp.json()["detail"]


def test_checkout_insufficient_stock(client, auth_headers, db_session, normal_user, sample_product):
    add_to_cart(db_session, normal_user, sample_product, quantity=sample_product.stock + 1)

    resp = client.post("/payments/checkout", json={**CHECKOUT_BODY, "payment_method": "anticipado"}, headers=auth_headers)
    assert resp.status_code == 400
    assert "Stock insuficiente" in resp.json()["detail"]


def test_checkout_anticipado_success(client, auth_headers, db_session, cart_item, sample_product):
    resp = client.post("/payments/checkout", json={**CHECKOUT_BODY, "payment_method": "anticipado"}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["flow"] == "bold"
    assert "signature" in body
    assert body["currency"] == "COP"

    order = db_session.query(Order).filter(Order.id == body["order_id"]).first()
    assert order.status == "pending"
    assert order.bold_order_id == body["bold_order_id"]

    db_session.refresh(sample_product)
    assert sample_product.stock == 10  # stock untouched until webhook confirms


def test_checkout_contraentrega_success(client, auth_headers, db_session, cart_item, sample_product):
    resp = client.post("/payments/checkout", json={**CHECKOUT_BODY, "payment_method": "contraentrega"}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["flow"] == "cod"

    order = db_session.query(Order).filter(Order.id == body["order_id"]).first()
    assert order.status == "cod_confirmed"
    assert order.dropi_status == "pending_manual"  # Dropi unconfigured in test env

    db_session.refresh(sample_product)
    assert sample_product.stock == 10 - cart_item.quantity

    cart_resp = client.get("/cart/", headers=auth_headers).json()
    assert cart_resp["items"] == []


def test_checkout_contraentrega_dropi_success(client, auth_headers, cart_item, db_session, monkeypatch):
    monkeypatch.setattr("routes.payments.create_dropi_order", lambda *a, **k: {"id": "dropi-999"})
    resp = client.post("/payments/checkout", json={**CHECKOUT_BODY, "payment_method": "contraentrega"}, headers=auth_headers)
    order = db_session.query(Order).filter(Order.id == resp.json()["order_id"]).first()
    assert order.dropi_status == "created"
    assert order.dropi_order_id == "dropi-999"


# ── /payments/bold/webhook ───────────────────────────────────────────────────

def _make_anticipado_order(client, auth_headers):
    resp = client.post("/payments/checkout", json={**CHECKOUT_BODY, "payment_method": "anticipado"}, headers=auth_headers)
    return resp.json()


def test_webhook_invalid_signature(client, auth_headers, cart_item):
    order = _make_anticipado_order(client, auth_headers)
    resp = send_bold_webhook(client, bold_approved_payload(order["bold_order_id"]), bad_signature=True)
    assert resp.status_code == 400


def test_webhook_missing_reference(client):
    resp = send_bold_webhook(client, {"type": "SALE_APPROVED", "data": {}})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


def test_webhook_order_not_found(client):
    resp = send_bold_webhook(client, bold_approved_payload("VLX-NOEXISTE-1"))
    assert resp.status_code == 200
    assert resp.json()["status"] == "order not found"


def test_webhook_approved_marks_paid_and_decrements_stock(client, auth_headers, cart_item, sample_product, db_session, mock_send_email):
    order = _make_anticipado_order(client, auth_headers)
    resp = send_bold_webhook(client, bold_approved_payload(order["bold_order_id"]))
    assert resp.status_code == 200

    db_order = db_session.query(Order).filter(Order.id == order["order_id"]).first()
    assert db_order.status == "paid"

    db_session.refresh(sample_product)
    assert sample_product.stock == 10 - cart_item.quantity

    cart_resp = client.get("/cart/", headers=auth_headers).json()
    assert cart_resp["items"] == []
    mock_send_email.assert_called_once()


def test_webhook_is_idempotent(client, auth_headers, cart_item, sample_product, db_session):
    order = _make_anticipado_order(client, auth_headers)
    send_bold_webhook(client, bold_approved_payload(order["bold_order_id"]))
    send_bold_webhook(client, bold_approved_payload(order["bold_order_id"]))

    db_session.refresh(sample_product)
    assert sample_product.stock == 10 - cart_item.quantity  # decremented only once

    db_order = db_session.query(Order).filter(Order.id == order["order_id"]).first()
    assert db_order.status == "paid"


def test_webhook_rejected_cancels_order(client, auth_headers, cart_item, db_session):
    order = _make_anticipado_order(client, auth_headers)
    resp = send_bold_webhook(client, bold_rejected_payload(order["bold_order_id"]))
    assert resp.status_code == 200

    db_order = db_session.query(Order).filter(Order.id == order["order_id"]).first()
    assert db_order.status == "cancelled"


def test_webhook_approved_dropi_success(client, auth_headers, cart_item, db_session, monkeypatch):
    monkeypatch.setattr("routes.payments.create_dropi_order", lambda *a, **k: {"id": "dropi-777"})
    order = _make_anticipado_order(client, auth_headers)
    send_bold_webhook(client, bold_approved_payload(order["bold_order_id"]))

    db_order = db_session.query(Order).filter(Order.id == order["order_id"]).first()
    assert db_order.dropi_status == "created"
    assert db_order.dropi_order_id == "dropi-777"


def test_webhook_unknown_event_type_no_status_change(client, auth_headers, cart_item, db_session):
    order = _make_anticipado_order(client, auth_headers)
    resp = send_bold_webhook(client, {
        "type": "ALGO_RARO_NO_DOCUMENTADO",
        "data": {"metadata": {"reference": order["bold_order_id"]}},
    })
    assert resp.status_code == 200

    db_order = db_session.query(Order).filter(Order.id == order["order_id"]).first()
    assert db_order.status == "pending"


# ── /payments/orders ─────────────────────────────────────────────────────────

def test_get_my_orders_isolated_per_user(client, auth_headers, admin_headers, cart_item):
    _make_anticipado_order(client, auth_headers)

    mine = client.get("/payments/orders", headers=auth_headers)
    assert len(mine.json()) == 1

    others = client.get("/payments/orders", headers=admin_headers)
    assert others.json() == []


def test_get_order_detail_not_owner_404(client, auth_headers, admin_headers, cart_item):
    order = _make_anticipado_order(client, auth_headers)

    own = client.get(f"/payments/orders/{order['order_id']}", headers=auth_headers)
    assert own.status_code == 200

    other = client.get(f"/payments/orders/{order['order_id']}", headers=admin_headers)
    assert other.status_code == 404


# ── /payments/admin/orders ───────────────────────────────────────────────────

def test_admin_orders_requires_admin(client, auth_headers):
    resp = client.get("/payments/admin/orders", headers=auth_headers)
    assert resp.status_code == 403


def test_admin_orders_lists_everything_with_filters(client, auth_headers, admin_headers, cart_item):
    order = _make_anticipado_order(client, auth_headers)
    send_bold_webhook(client, bold_approved_payload(order["bold_order_id"]))

    all_orders = client.get("/payments/admin/orders", headers=admin_headers).json()
    assert len(all_orders) == 1

    paid_only = client.get("/payments/admin/orders?status_filter=paid", headers=admin_headers).json()
    assert len(paid_only) == 1

    pending_only = client.get("/payments/admin/orders?status_filter=pending", headers=admin_headers).json()
    assert pending_only == []

    by_payment_method = client.get("/payments/admin/orders?payment_method=anticipado", headers=admin_headers).json()
    assert len(by_payment_method) == 1
    none_by_payment_method = client.get("/payments/admin/orders?payment_method=contraentrega", headers=admin_headers).json()
    assert none_by_payment_method == []

    matching_search = client.get(
        f"/payments/admin/orders?search={order['order_id'][:8]}", headers=admin_headers
    ).json()
    assert len(matching_search) == 1
    no_match_search = client.get("/payments/admin/orders?search=no-deberia-existir", headers=admin_headers).json()
    assert no_match_search == []


def test_admin_patch_order_status_invalid(client, admin_headers, auth_headers, cart_item):
    order = _make_anticipado_order(client, auth_headers)
    resp = client.patch(
        f"/payments/admin/orders/{order['order_id']}", json={"status": "no-es-un-estado"}, headers=admin_headers
    )
    assert resp.status_code == 400


def test_admin_patch_order_not_found(client, admin_headers):
    resp = client.patch(
        "/payments/admin/orders/00000000-0000-0000-0000-000000000000",
        json={"status": "paid"},
        headers=admin_headers,
    )
    assert resp.status_code == 404


def test_admin_patch_order_status_requires_admin(client, auth_headers, cart_item):
    order = _make_anticipado_order(client, auth_headers)
    resp = client.patch(
        f"/payments/admin/orders/{order['order_id']}", json={"status": "paid"}, headers=auth_headers
    )
    assert resp.status_code == 403


def test_admin_patch_pending_to_paid_replicates_webhook_side_effects(
    client, admin_headers, auth_headers, cart_item, sample_product, db_session, mock_send_email
):
    order = _make_anticipado_order(client, auth_headers)
    resp = client.patch(
        f"/payments/admin/orders/{order['order_id']}", json={"status": "paid"}, headers=admin_headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "paid"

    db_session.refresh(sample_product)
    assert sample_product.stock == 10 - cart_item.quantity
    mock_send_email.assert_called_once()

    # patching again shouldn't double-decrement stock (previous_status is no longer "pending")
    client.patch(f"/payments/admin/orders/{order['order_id']}", json={"status": "paid"}, headers=admin_headers)
    db_session.refresh(sample_product)
    assert sample_product.stock == 10 - cart_item.quantity
