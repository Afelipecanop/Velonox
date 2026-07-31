from datetime import datetime, timedelta, timezone

from services.auth import create_password_reset_token, hash_password
from models.password_reset_token import PasswordResetToken
from tests.conftest import TEST_PASSWORD


def test_register_success(client):
    resp = client.post("/auth/register", json={
        "email": "nuevo@example.com",
        "password": "cualquiercosa",
        "full_name": "Nuevo Usuario",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "nuevo@example.com"
    assert body["is_admin"] is False
    assert body["is_active"] is True
    assert "id" in body
    assert "password" not in body
    assert "hashed_password" not in body


def test_register_creates_cart(client):
    resp = client.post("/auth/register", json={
        "email": "conCarrito@example.com",
        "password": "cualquiercosa",
        "full_name": "Con Carrito",
    })
    login = client.post("/auth/login", json={
        "email": "conCarrito@example.com", "password": "cualquiercosa",
    })
    token = login.json()["access_token"]
    cart_resp = client.get("/cart/", headers={"Authorization": f"Bearer {token}"})
    assert cart_resp.status_code == 200
    assert cart_resp.json()["items"] == []


def test_register_duplicate_email(client, normal_user):
    resp = client.post("/auth/register", json={
        "email": normal_user.email,
        "password": "otra_pass",
        "full_name": "Otro Nombre",
    })
    assert resp.status_code == 400
    assert "ya está registrado" in resp.json()["detail"]


def test_register_invalid_email_format(client):
    resp = client.post("/auth/register", json={
        "email": "no-es-un-email",
        "password": "cualquiercosa",
        "full_name": "X",
    })
    assert resp.status_code == 422


def test_login_success(client, normal_user):
    resp = client.post("/auth/login", json={
        "email": normal_user.email, "password": TEST_PASSWORD,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 0


def test_login_wrong_password(client, normal_user):
    resp = client.post("/auth/login", json={
        "email": normal_user.email, "password": "incorrecta",
    })
    assert resp.status_code == 401


def test_login_nonexistent_email(client):
    resp = client.post("/auth/login", json={
        "email": "no-existe@example.com", "password": "loquesea",
    })
    assert resp.status_code == 401


def test_me_with_valid_token(client, normal_user, auth_headers):
    resp = client.get("/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == normal_user.email


def test_me_without_token(client):
    resp = client.get("/auth/me")
    assert resp.status_code in (401, 403)


def test_me_with_invalid_token(client):
    resp = client.get("/auth/me", headers={"Authorization": "Bearer esto-no-es-un-jwt"})
    assert resp.status_code == 401


def test_me_inactive_user_rejected(client, make_user):
    user = make_user(email="inactivo@example.com", is_active=False)
    from services.auth import create_access_token
    token = create_access_token(data={"sub": str(user.id)})
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_forgot_password_existing_user_sends_email(client, normal_user, mock_send_email):
    resp = client.post("/auth/forgot-password", json={"email": normal_user.email})
    assert resp.status_code == 200
    mock_send_email.assert_called_once()


def test_forgot_password_unknown_email_same_generic_response(client, mock_send_email):
    resp = client.post("/auth/forgot-password", json={"email": "fantasma@example.com"})
    assert resp.status_code == 200
    mock_send_email.assert_not_called()


def test_forgot_password_google_user_no_email_sent(client, make_user, mock_send_email):
    user = make_user(email="google@example.com", auth_provider="google")
    resp = client.post("/auth/forgot-password", json={"email": user.email})
    assert resp.status_code == 200
    mock_send_email.assert_not_called()


def test_reset_password_valid_token(client, db_session, normal_user):
    raw_token = create_password_reset_token(db_session, normal_user)
    resp = client.post("/auth/reset-password", json={
        "token": raw_token, "new_password": "NuevaPass123!",
    })
    assert resp.status_code == 200

    login_old = client.post("/auth/login", json={
        "email": normal_user.email, "password": TEST_PASSWORD,
    })
    assert login_old.status_code == 401

    login_new = client.post("/auth/login", json={
        "email": normal_user.email, "password": "NuevaPass123!",
    })
    assert login_new.status_code == 200


def test_reset_password_invalid_token(client):
    resp = client.post("/auth/reset-password", json={
        "token": "token-que-no-existe", "new_password": "NuevaPass123!",
    })
    assert resp.status_code == 400


def test_reset_password_expired_token(client, db_session, normal_user):
    from services.auth import _hash_reset_token
    import secrets
    raw_token = secrets.token_urlsafe(32)
    expired = PasswordResetToken(
        user_id=normal_user.id,
        token_hash=_hash_reset_token(raw_token),
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db_session.add(expired)
    db_session.commit()

    resp = client.post("/auth/reset-password", json={
        "token": raw_token, "new_password": "NuevaPass123!",
    })
    assert resp.status_code == 400


def test_reset_password_already_used_token(client, db_session, normal_user):
    raw_token = create_password_reset_token(db_session, normal_user)
    first = client.post("/auth/reset-password", json={
        "token": raw_token, "new_password": "PrimeraVez123!",
    })
    assert first.status_code == 200

    second = client.post("/auth/reset-password", json={
        "token": raw_token, "new_password": "SegundaVez123!",
    })
    assert second.status_code == 400


def test_google_login_new_user(client, monkeypatch):
    monkeypatch.setattr(
        "routes.auth.verify_google_token",
        lambda token: {"email": "desdegoogle@example.com", "name": "Google User"},
    )
    resp = client.post("/auth/google", json={"id_token": "cualquier-token"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_google_login_invalid_token(client, monkeypatch):
    def _raise(token):
        raise ValueError("token inválido")
    monkeypatch.setattr("routes.auth.verify_google_token", _raise)
    resp = client.post("/auth/google", json={"id_token": "malo"})
    assert resp.status_code == 401


def test_google_login_existing_inactive_user(client, monkeypatch, make_user):
    user = make_user(email="inactivogoogle@example.com", auth_provider="google", is_active=False)
    monkeypatch.setattr(
        "routes.auth.verify_google_token",
        lambda token: {"email": user.email, "name": "Google User"},
    )
    resp = client.post("/auth/google", json={"id_token": "cualquiera"})
    assert resp.status_code == 403
