from models.product import Product
from models.product_variant import ProductVariant
from models.product_image import ProductImage


# ── Productos ────────────────────────────────────────────────────────────────

def test_list_products_only_active(client, db_session, sample_product, sample_category):
    inactive = Product(name="Descontinuado", price=9.99, stock=0, is_active=False)
    db_session.add(inactive)
    db_session.commit()

    resp = client.get("/products/")
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()]
    assert str(sample_product.id) in ids
    assert str(inactive.id) not in ids


def test_get_product_detail(client, sample_product):
    resp = client.get(f"/products/{sample_product.id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == sample_product.name


def test_get_product_not_found(client):
    resp = client.get("/products/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def test_get_inactive_product_404(client, db_session):
    p = Product(name="Oculto", price=1.0, stock=0, is_active=False)
    db_session.add(p)
    db_session.commit()
    resp = client.get(f"/products/{p.id}")
    assert resp.status_code == 404


def test_create_product_requires_admin(client, auth_headers):
    resp = client.post("/products/", json={
        "name": "Sarten", "price": 20.0, "stock": 5,
    }, headers=auth_headers)
    assert resp.status_code == 403


def test_create_product_requires_token(client):
    resp = client.post("/products/", json={"name": "Sarten", "price": 20.0, "stock": 5})
    assert resp.status_code in (401, 403)


def test_create_product_as_admin(client, admin_headers):
    resp = client.post("/products/", json={
        "name": "Sarten grande", "price": 35.5, "stock": 8, "category": "sartenes",
    }, headers=admin_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Sarten grande"
    assert body["stock"] == 8


def test_update_product_as_admin(client, admin_headers, sample_product):
    resp = client.put(f"/products/{sample_product.id}", json={"price": 59.99}, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["price"] == 59.99
    assert resp.json()["name"] == sample_product.name


def test_update_product_not_found(client, admin_headers):
    resp = client.put(
        "/products/00000000-0000-0000-0000-000000000000",
        json={"price": 1.0},
        headers=admin_headers,
    )
    assert resp.status_code == 404


def test_update_product_requires_admin(client, auth_headers, sample_product):
    resp = client.put(f"/products/{sample_product.id}", json={"price": 1.0}, headers=auth_headers)
    assert resp.status_code == 403


def test_delete_product_soft_deletes(client, admin_headers, sample_product):
    resp = client.delete(f"/products/{sample_product.id}", headers=admin_headers)
    assert resp.status_code == 204

    follow_up = client.get(f"/products/{sample_product.id}")
    assert follow_up.status_code == 404


def test_delete_product_requires_admin(client, auth_headers, sample_product):
    resp = client.delete(f"/products/{sample_product.id}", headers=auth_headers)
    assert resp.status_code == 403


# ── Variantes ────────────────────────────────────────────────────────────────

def test_create_variant_as_admin(client, admin_headers, sample_product):
    resp = client.post(
        f"/products/{sample_product.id}/variants",
        json={"name": "Rojo", "stock": 3},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Rojo"
    assert body["product_id"] == str(sample_product.id)


def test_create_variant_requires_admin(client, auth_headers, sample_product):
    resp = client.post(
        f"/products/{sample_product.id}/variants",
        json={"name": "Rojo", "stock": 3},
        headers=auth_headers,
    )
    assert resp.status_code == 403


def test_create_variant_product_not_found(client, admin_headers):
    resp = client.post(
        "/products/00000000-0000-0000-0000-000000000000/variants",
        json={"name": "Rojo", "stock": 3},
        headers=admin_headers,
    )
    assert resp.status_code == 404


def test_list_variants_only_active(client, db_session, sample_product):
    active = ProductVariant(product_id=sample_product.id, name="Verde", stock=1, is_active=True)
    inactive = ProductVariant(product_id=sample_product.id, name="Azul", stock=1, is_active=False)
    db_session.add_all([active, inactive])
    db_session.commit()

    resp = client.get(f"/products/{sample_product.id}/variants")
    assert resp.status_code == 200
    names = [v["name"] for v in resp.json()]
    assert "Verde" in names
    assert "Azul" not in names


def test_delete_variant_soft_deletes_and_hides_from_product_response(client, admin_headers, sample_product):
    create = client.post(
        f"/products/{sample_product.id}/variants",
        json={"name": "Negro", "stock": 2},
        headers=admin_headers,
    )
    variant_id = create.json()["id"]

    delete = client.delete(
        f"/products/{sample_product.id}/variants/{variant_id}", headers=admin_headers
    )
    assert delete.status_code == 204

    product_resp = client.get(f"/products/{sample_product.id}")
    variant_ids = [v["id"] for v in product_resp.json()["variants"]]
    assert variant_id not in variant_ids


def test_update_variant_not_found(client, admin_headers, sample_product):
    resp = client.put(
        f"/products/{sample_product.id}/variants/00000000-0000-0000-0000-000000000000",
        json={"name": "X"},
        headers=admin_headers,
    )
    assert resp.status_code == 404


def test_update_variant_success(client, admin_headers, sample_product):
    created = client.post(
        f"/products/{sample_product.id}/variants", json={"name": "Original", "stock": 1}, headers=admin_headers
    ).json()
    resp = client.put(
        f"/products/{sample_product.id}/variants/{created['id']}",
        json={"name": "Renombrada", "stock": 9},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renombrada"
    assert resp.json()["stock"] == 9


def test_delete_variant_not_found(client, admin_headers, sample_product):
    resp = client.delete(
        f"/products/{sample_product.id}/variants/00000000-0000-0000-0000-000000000000",
        headers=admin_headers,
    )
    assert resp.status_code == 404


# ── Imágenes ─────────────────────────────────────────────────────────────────

def test_first_image_becomes_primary_and_syncs_product_image_url(client, admin_headers, sample_product, db_session):
    resp = client.post(
        f"/products/{sample_product.id}/images",
        json={"url": "https://example.com/foto1.jpg"},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["is_primary"] is True

    db_session.refresh(sample_product)
    assert sample_product.image_url == "https://example.com/foto1.jpg"


def test_second_image_not_primary(client, admin_headers, sample_product):
    client.post(f"/products/{sample_product.id}/images", json={"url": "https://example.com/1.jpg"}, headers=admin_headers)
    second = client.post(f"/products/{sample_product.id}/images", json={"url": "https://example.com/2.jpg"}, headers=admin_headers)
    assert second.json()["is_primary"] is False


def test_set_primary_image_switches_and_syncs(client, admin_headers, sample_product, db_session):
    first = client.post(f"/products/{sample_product.id}/images", json={"url": "https://example.com/1.jpg"}, headers=admin_headers)
    second = client.post(f"/products/{sample_product.id}/images", json={"url": "https://example.com/2.jpg"}, headers=admin_headers)

    set_primary = client.post(
        f"/products/{sample_product.id}/images/{second.json()['id']}/set-primary",
        headers=admin_headers,
    )
    assert set_primary.status_code == 200
    assert set_primary.json()["is_primary"] is True

    images = client.get(f"/products/{sample_product.id}/images").json()
    primaries = [i for i in images if i["is_primary"]]
    assert len(primaries) == 1
    assert primaries[0]["id"] == second.json()["id"]

    db_session.refresh(sample_product)
    assert sample_product.image_url == "https://example.com/2.jpg"


def test_delete_image_nulls_linked_variant_image_id(client, admin_headers, sample_product, db_session):
    image = client.post(
        f"/products/{sample_product.id}/images", json={"url": "https://example.com/1.jpg"}, headers=admin_headers
    ).json()
    variant = ProductVariant(product_id=sample_product.id, name="Con foto", stock=1, image_id=image["id"])
    db_session.add(variant)
    db_session.commit()

    delete = client.delete(f"/products/{sample_product.id}/images/{image['id']}", headers=admin_headers)
    assert delete.status_code == 204

    db_session.refresh(variant)
    assert variant.image_id is None


def test_images_admin_only(client, auth_headers, sample_product):
    resp = client.post(
        f"/products/{sample_product.id}/images", json={"url": "x"}, headers=auth_headers
    )
    assert resp.status_code == 403


def test_get_images_product_not_found(client):
    resp = client.get("/products/00000000-0000-0000-0000-000000000000/images")
    assert resp.status_code == 404


def test_update_image_not_found(client, admin_headers, sample_product):
    resp = client.put(
        f"/products/{sample_product.id}/images/00000000-0000-0000-0000-000000000000",
        json={"url": "https://example.com/nueva.jpg"},
        headers=admin_headers,
    )
    assert resp.status_code == 404


def test_update_primary_image_url_syncs_product(client, admin_headers, sample_product, db_session):
    image = client.post(
        f"/products/{sample_product.id}/images", json={"url": "https://example.com/1.jpg"}, headers=admin_headers
    ).json()

    resp = client.put(
        f"/products/{sample_product.id}/images/{image['id']}",
        json={"url": "https://example.com/actualizada.jpg"},
        headers=admin_headers,
    )
    assert resp.status_code == 200

    db_session.refresh(sample_product)
    assert sample_product.image_url == "https://example.com/actualizada.jpg"
