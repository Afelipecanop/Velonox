from models.cart import Cart, CartItem


def test_get_empty_cart(client, auth_headers):
    resp = client.get("/cart/", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_get_cart_requires_token(client):
    resp = client.get("/cart/")
    assert resp.status_code in (401, 403)


def test_add_item_to_cart(client, auth_headers, sample_product):
    resp = client.post("/cart/items", json={
        "product_id": str(sample_product.id), "quantity": 2,
    }, headers=auth_headers)
    assert resp.status_code == 201

    cart = client.get("/cart/", headers=auth_headers).json()
    assert len(cart["items"]) == 1
    assert cart["items"][0]["quantity"] == 2
    assert cart["total"] == sample_product.price * 2


def test_add_item_sums_quantity_if_already_present(client, auth_headers, sample_product):
    client.post("/cart/items", json={"product_id": str(sample_product.id), "quantity": 2}, headers=auth_headers)
    client.post("/cart/items", json={"product_id": str(sample_product.id), "quantity": 3}, headers=auth_headers)

    cart = client.get("/cart/", headers=auth_headers).json()
    assert len(cart["items"]) == 1
    assert cart["items"][0]["quantity"] == 5


def test_add_item_insufficient_stock(client, auth_headers, sample_product):
    resp = client.post("/cart/items", json={
        "product_id": str(sample_product.id), "quantity": sample_product.stock + 1,
    }, headers=auth_headers)
    assert resp.status_code == 400
    assert "Stock insuficiente" in resp.json()["detail"]


def test_add_item_product_not_found(client, auth_headers):
    resp = client.post("/cart/items", json={
        "product_id": "00000000-0000-0000-0000-000000000000", "quantity": 1,
    }, headers=auth_headers)
    assert resp.status_code == 404


def test_add_item_inactive_product(client, auth_headers, db_session):
    from models.product import Product
    inactive = Product(name="Oculto", price=1.0, stock=5, is_active=False)
    db_session.add(inactive)
    db_session.commit()

    resp = client.post("/cart/items", json={
        "product_id": str(inactive.id), "quantity": 1,
    }, headers=auth_headers)
    assert resp.status_code == 404


def test_update_cart_item_quantity(client, auth_headers, cart_item):
    resp = client.put(f"/cart/items/{cart_item.id}", json={"quantity": 5}, headers=auth_headers)
    assert resp.status_code == 200

    cart = client.get("/cart/", headers=auth_headers).json()
    assert cart["items"][0]["quantity"] == 5


def test_update_cart_item_to_zero_deletes_it(client, auth_headers, cart_item):
    resp = client.put(f"/cart/items/{cart_item.id}", json={"quantity": 0}, headers=auth_headers)
    assert resp.status_code == 200

    cart = client.get("/cart/", headers=auth_headers).json()
    assert cart["items"] == []


def test_update_cart_item_not_found(client, auth_headers):
    resp = client.put(
        "/cart/items/00000000-0000-0000-0000-000000000000",
        json={"quantity": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_update_other_users_cart_item_forbidden(client, admin_headers, cart_item):
    resp = client.put(f"/cart/items/{cart_item.id}", json={"quantity": 1}, headers=admin_headers)
    assert resp.status_code == 404


def test_remove_cart_item(client, auth_headers, cart_item):
    resp = client.delete(f"/cart/items/{cart_item.id}", headers=auth_headers)
    assert resp.status_code == 204

    cart = client.get("/cart/", headers=auth_headers).json()
    assert cart["items"] == []


def test_remove_cart_item_not_found(client, auth_headers):
    resp = client.delete("/cart/items/00000000-0000-0000-0000-000000000000", headers=auth_headers)
    assert resp.status_code == 404


def test_remove_other_users_cart_item_forbidden(client, admin_headers, cart_item):
    resp = client.delete(f"/cart/items/{cart_item.id}", headers=admin_headers)
    assert resp.status_code == 404
