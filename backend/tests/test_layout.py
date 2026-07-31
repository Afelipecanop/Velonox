def new_block(block_id="block-1", block_type="text_section", order_index=0, text="hola"):
    return {
        "id": block_id,
        "block_type": block_type,
        "order_index": order_index,
        "config": {"text": text},
        "is_visible": True,
    }


def test_get_layout_home_seeds_default_blocks(client):
    resp = client.get("/layout/?page=home")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) > 0
    assert any(b["block_type"] == "hero_banner" for b in body)


def test_get_layout_does_not_reseed_on_second_call(client):
    first = client.get("/layout/?page=home").json()
    second = client.get("/layout/?page=home").json()
    assert len(first) == len(second)


def test_get_layout_content_page_seeds_from_content_defaults(client):
    resp = client.get("/layout/?page=contacto")
    assert resp.status_code == 200
    assert len(resp.json()) > 0


def test_get_layout_unknown_page_seeds_empty(client):
    resp = client.get("/layout/?page=pagina-inexistente")
    assert resp.status_code == 200
    assert resp.json() == []


def test_update_layout_requires_admin(client, auth_headers):
    resp = client.put("/layout/?page=home", json={"blocks": [new_block()]}, headers=auth_headers)
    assert resp.status_code == 403


def test_update_layout_saves_blocks(client, admin_headers):
    resp = client.put("/layout/?page=home", json={"blocks": [new_block(text="version 1")]}, headers=admin_headers)
    assert resp.status_code == 200

    layout = client.get("/layout/?page=home").json()
    assert len(layout) == 1
    assert layout[0]["config"]["text"] == "version 1"


def test_update_layout_archives_previous_state_in_history(client, admin_headers):
    client.get("/layout/?page=home")  # seeds DEFAULT_BLOCKS

    client.put("/layout/?page=home", json={"blocks": [new_block(text="v1")]}, headers=admin_headers)

    history = client.get("/layout/history?page=home", headers=admin_headers).json()
    assert len(history) == 1  # the seeded DEFAULT_BLOCKS state got archived


def test_history_requires_admin(client, auth_headers):
    resp = client.get("/layout/history?page=home", headers=auth_headers)
    assert resp.status_code == 403


def test_restore_previous_version(client, admin_headers):
    client.get("/layout/?page=home")  # seed
    client.put("/layout/?page=home", json={"blocks": [new_block(text="v1")]}, headers=admin_headers)

    history = client.get("/layout/history?page=home", headers=admin_headers).json()
    original_version_id = history[0]["id"]

    restore = client.post(f"/layout/restore/{original_version_id}", headers=admin_headers)
    assert restore.status_code == 200

    layout = client.get("/layout/?page=home").json()
    assert any(b["block_type"] == "hero_banner" for b in layout)  # back to DEFAULT_BLOCKS

    history_after = client.get("/layout/history?page=home", headers=admin_headers).json()
    assert len(history_after) == 2  # restore also archives the pre-restore ("v1") state


def test_restore_not_found(client, admin_headers):
    resp = client.post("/layout/restore/no-existe", headers=admin_headers)
    assert resp.status_code == 404


def test_history_prunes_versions_beyond_max(client, admin_headers):
    client.get("/layout/?page=home")  # seed, so the first PUT has something to archive
    for i in range(25):
        client.put("/layout/?page=home", json={"blocks": [new_block(text=f"v{i}")]}, headers=admin_headers)

    history = client.get("/layout/history?page=home", headers=admin_headers).json()
    assert len(history) == 20  # MAX_HISTORY_PER_PAGE


def test_restore_requires_admin(client, auth_headers):
    resp = client.post("/layout/restore/algun-id", headers=auth_headers)
    assert resp.status_code == 403


def test_reset_layout_reseeds_defaults_on_next_get(client, admin_headers):
    client.put("/layout/?page=home", json={"blocks": [new_block(text="custom")]}, headers=admin_headers)

    reset = client.post("/layout/reset?page=home", headers=admin_headers)
    assert reset.status_code == 200

    layout = client.get("/layout/?page=home").json()
    assert any(b["block_type"] == "hero_banner" for b in layout)


def test_reset_requires_admin(client, auth_headers):
    resp = client.post("/layout/reset?page=home", headers=auth_headers)
    assert resp.status_code == 403


def test_add_block(client, admin_headers):
    client.get("/layout/?page=home")
    resp = client.post(
        "/layout/blocks?page=home",
        json={"id": "extra", "block_type": "testimonials", "order_index": 99, "config": {}, "is_visible": True},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["block_type"] == "testimonials"


def test_add_block_requires_admin(client, auth_headers):
    resp = client.post(
        "/layout/blocks?page=home",
        json={"id": "extra", "block_type": "testimonials", "order_index": 0, "config": {}, "is_visible": True},
        headers=auth_headers,
    )
    assert resp.status_code == 403


def test_delete_block(client, admin_headers):
    client.get("/layout/?page=home")
    added = client.post(
        "/layout/blocks?page=home",
        json={"id": "para-borrar", "block_type": "testimonials", "order_index": 0, "config": {}, "is_visible": True},
        headers=admin_headers,
    ).json()

    resp = client.delete(f"/layout/blocks/{added['id']}", headers=admin_headers)
    assert resp.status_code == 200

    layout = client.get("/layout/?page=home").json()
    assert added["id"] not in [b["id"] for b in layout]
