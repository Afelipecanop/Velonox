import pytest

from models.product import Product
from models.category import Category


def test_get_categories_seeds_defaults_when_empty(client):
    resp = client.get("/categories/")
    assert resp.status_code == 200
    slugs = [c["slug"] for c in resp.json()]
    assert "ollas" in slugs
    assert "sartenes" in slugs
    assert "utensilios" in slugs
    assert "accesorios" in slugs


def test_get_categories_does_not_reseed_on_second_call(client):
    first = client.get("/categories/").json()
    second = client.get("/categories/").json()
    assert len(first) == len(second)


def test_get_category_by_slug(client, sample_category):
    resp = client.get(f"/categories/{sample_category.slug}")
    assert resp.status_code == 200
    assert resp.json()["name"] == sample_category.name


def test_get_category_not_found(client):
    resp = client.get("/categories/no-existe")
    assert resp.status_code == 404


def test_get_products_by_category(client, db_session, sample_category, sample_product):
    other_cat_product = Product(name="Otro", price=1.0, stock=1, category="otra-categoria")
    db_session.add(other_cat_product)
    db_session.commit()

    resp = client.get(f"/categories/{sample_category.slug}/products")
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()]
    assert str(sample_product.id) in ids
    assert str(other_cat_product.id) not in ids


def test_get_products_by_category_not_found(client):
    resp = client.get("/categories/no-existe/products")
    assert resp.status_code == 404


def test_create_category_as_admin(client, admin_headers):
    resp = client.post("/categories/", json={
        "slug": "nueva-cat", "name": "Nueva Categoria",
    }, headers=admin_headers)
    assert resp.status_code == 201
    assert resp.json()["slug"] == "nueva-cat"


def test_create_category_duplicate_slug(client, admin_headers, sample_category):
    resp = client.post("/categories/", json={
        "slug": sample_category.slug, "name": "Duplicada",
    }, headers=admin_headers)
    assert resp.status_code == 400


def test_create_category_requires_admin(client, auth_headers):
    resp = client.post("/categories/", json={"slug": "x", "name": "X"}, headers=auth_headers)
    assert resp.status_code == 403


def test_create_category_requires_token(client):
    resp = client.post("/categories/", json={"slug": "x", "name": "X"})
    assert resp.status_code in (401, 403)


def test_update_category_as_admin(client, admin_headers, sample_category):
    resp = client.put(f"/categories/{sample_category.slug}", json={"name": "Nombre Nuevo"}, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Nombre Nuevo"


def test_update_category_not_found(client, admin_headers):
    resp = client.put("/categories/no-existe", json={"name": "X"}, headers=admin_headers)
    assert resp.status_code == 404


def test_delete_category_soft_deletes(client, admin_headers, sample_category):
    resp = client.delete(f"/categories/{sample_category.slug}", headers=admin_headers)
    assert resp.status_code == 204

    listing = client.get("/categories/").json()
    slugs = [c["slug"] for c in listing]
    assert sample_category.slug not in slugs


def test_delete_category_requires_admin(client, auth_headers, sample_category):
    resp = client.delete(f"/categories/{sample_category.slug}", headers=auth_headers)
    assert resp.status_code == 403


@pytest.mark.xfail(
    reason=(
        "Bug real en routes/categories.py: get_categories() reseedea DEFAULT_CATEGORIES "
        "cuando 'not cats' (activas), no cuando la tabla está vacía. Si la última categoría "
        "activa restante tiene un slug que coincide con uno de los defaults (ej. 'ollas') y "
        "se desactiva, el siguiente GET /categories/ intenta reinsertar ese slug y revienta "
        "con IntegrityError de PK duplicada en vez de devolver una lista vacía o reseedear "
        "limpiamente. No se corrigió aquí (solo testing, ver instrucciones)."
    ),
    strict=True,
)
def test_delete_last_active_default_slug_category_crashes_reseed(client, admin_headers, db_session):
    db_session.add(Category(slug="ollas", name="Ollas y cacerolas", order_index=0))
    db_session.commit()

    delete = client.delete("/categories/ollas", headers=admin_headers)
    assert delete.status_code == 204

    resp = client.get("/categories/")
    assert resp.status_code == 200
