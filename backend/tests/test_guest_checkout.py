from models.order import Order
from models.user import User


def guest_payload(email="invitado@example.com", payment_method="contraentrega", items=None, product_id=None, quantity=1):
    return {
        "email": email,
        "nombre": "Invitado Prueba",
        "document_type": "CC",
        "document_number": "999888777",
        "payment_method": payment_method,
        "shipping_address": {
            "direccion": "Calle Falsa 123",
            "ciudad": "Bogota",
            "departamento": "Cundinamarca",
            "telefono": "3009998877",
        },
        "items": items if items is not None else [{"product_id": str(product_id), "quantity": quantity}],
    }


def test_guest_checkout_empty_items(client):
    resp = client.post("/guest/checkout", json=guest_payload(items=[]))
    assert resp.status_code == 400


def test_guest_checkout_product_not_found(client):
    resp = client.post("/guest/checkout", json=guest_payload(product_id="00000000-0000-0000-0000-000000000000"))
    assert resp.status_code == 404


def test_guest_checkout_insufficient_stock(client, sample_product):
    resp = client.post("/guest/checkout", json=guest_payload(product_id=sample_product.id, quantity=sample_product.stock + 1))
    assert resp.status_code == 400
    assert "Stock insuficiente" in resp.json()["detail"]


def test_guest_checkout_new_email_creates_user_and_sends_welcome(client, sample_product, db_session, mock_send_email):
    resp = client.post("/guest/checkout", json=guest_payload(email="nuevoinvitado@example.com", product_id=sample_product.id))
    assert resp.status_code == 200
    body = resp.json()
    assert body["cuenta_creada"] is True

    user = db_session.query(User).filter(User.email == "nuevoinvitado@example.com").first()
    assert user is not None
    assert mock_send_email.call_count >= 1  # welcome email + confirmation email (contraentrega)


def test_guest_checkout_existing_email_reuses_user(client, sample_product, normal_user, mock_send_email):
    resp = client.post("/guest/checkout", json=guest_payload(email=normal_user.email, product_id=sample_product.id))
    assert resp.status_code == 200
    body = resp.json()
    assert body["cuenta_creada"] is False


def test_guest_checkout_contraentrega_decrements_stock_and_confirms(client, sample_product, db_session):
    resp = client.post("/guest/checkout", json=guest_payload(
        payment_method="contraentrega", product_id=sample_product.id, quantity=3,
    ))
    assert resp.status_code == 200
    body = resp.json()
    assert body["flow"] == "cod"

    order = db_session.query(Order).filter(Order.id == body["order_id"]).first()
    assert order.status == "cod_confirmed"

    db_session.refresh(sample_product)
    assert sample_product.stock == 10 - 3


def test_guest_checkout_anticipado_does_not_touch_stock(client, sample_product, db_session):
    resp = client.post("/guest/checkout", json=guest_payload(
        payment_method="anticipado", product_id=sample_product.id, quantity=2,
    ))
    assert resp.status_code == 200
    body = resp.json()
    assert body["flow"] == "bold"
    assert "signature" in body

    db_session.refresh(sample_product)
    assert sample_product.stock == 10

    order = db_session.query(Order).filter(Order.id == body["order_id"]).first()
    assert order.status == "pending"


def test_guest_checkout_dropi_failure_marks_pending_manual(client, sample_product, db_session):
    resp = client.post("/guest/checkout", json=guest_payload(
        payment_method="contraentrega", product_id=sample_product.id,
    ))
    order = db_session.query(Order).filter(Order.id == resp.json()["order_id"]).first()
    assert order.dropi_status == "pending_manual"  # Dropi unconfigured in test env
