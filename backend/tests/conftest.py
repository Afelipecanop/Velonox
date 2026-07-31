import os

# Must run before any app module is imported: database.py, services/auth.py,
# services/bold.py etc. read these at import time via os.getenv()/load_dotenv().
# load_dotenv() never overrides a key that's already in os.environ, so setting
# these here guarantees the real backend/.env (prod/dev DATABASE_URL, real
# secrets) is never touched by the test suite.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("BOLD_SECRET_KEY", "test-bold-secret")
os.environ.setdefault("BOLD_API_KEY", "test-bold-api-key")
os.environ.setdefault("DROPI_BASE_URL", "")
os.environ.setdefault("DROPI_API_KEY", "")
os.environ.setdefault("RESEND_API_KEY", "test-resend-key")
os.environ.setdefault("EMAILS_FROM", "Velonox <hola@velonox.co>")
os.environ.setdefault("FRONTEND_URL", "https://velonox.co")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-google-client-id")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")

import datetime as dt
import uuid
import uuid as uuid_module
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, event, types
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from database import Base, get_db
import models  # noqa: F401 - import side effect registers every table on Base.metadata
from main import app
from models.user import User
from models.category import Category
from models.product import Product
from models.cart import Cart, CartItem
from models.password_reset_token import PasswordResetToken
from services.auth import hash_password, create_access_token

TEST_PASSWORD = "SuperSecreta123!"


def _sqlite_expires_at_is_tz_aware(target, context, attrs=None):
    # Postgres timestamptz always round-trips tz-aware; SQLite has no such type
    # and hands back naive datetimes, which breaks the aware-vs-naive comparison
    # in services/auth.get_valid_reset_token(). Only fires under the SQLite test
    # engine - real Postgres already returns aware datetimes, so this is a no-op
    # there (the `if` below simply never matches).
    if target.expires_at is not None and target.expires_at.tzinfo is None:
        target.expires_at = target.expires_at.replace(tzinfo=dt.timezone.utc)


# "load" fires for a brand-new identity-mapped instance; "refresh" fires when an
# already-mapped instance's expired attributes are re-fetched (e.g. after a test
# fixture's own db_session.commit() expired it) - need both.
event.listens_for(PasswordResetToken, "load")(_sqlite_expires_at_is_tz_aware)
event.listens_for(PasswordResetToken, "refresh")(_sqlite_expires_at_is_tz_aware)


class _SQLiteLenientUUID(types.TypeDecorator):
    """Real psycopg2 accepts plain strings for UUID columns; SQLite's fallback
    UUID emulation only accepts uuid.UUID instances, which breaks code (e.g.
    middleware/auth.py) that filters User.id by the raw str JWT subject."""
    impl = types.CHAR(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return uuid_module.UUID(value)


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    engine.dialect.colspecs = dict(engine.dialect.colspecs)
    engine.dialect.colspecs[PGUUID] = _SQLiteLenientUUID

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_connection, connection_record):
        # SQLite ignores FK constraints (ondelete=SET NULL/CASCADE) unless this
        # pragma is on per-connection; Postgres enforces them always.
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    # Reuses the same Session the test fixtures write with, rather than opening
    # a second one on the same StaticPool connection (SQLite only tolerates one
    # open transaction per connection at a time).
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_send_email(monkeypatch):
    """Safety net: never let a test hit the real Resend API."""
    mock = Mock(return_value=True)
    monkeypatch.setattr("services.email.send_email", mock)
    return mock


@pytest.fixture()
def make_user(db_session):
    def _make(email=None, password=TEST_PASSWORD, is_admin=False, full_name="Test User",
              is_active=True, auth_provider="local"):
        email = email or f"user-{uuid.uuid4().hex[:8]}@example.com"
        user = User(
            email=email,
            hashed_password=hash_password(password) if auth_provider == "local" else None,
            full_name=full_name,
            is_admin=is_admin,
            is_active=is_active,
            auth_provider=auth_provider,
        )
        db_session.add(user)
        db_session.flush()
        db_session.add(Cart(user_id=user.id))
        db_session.commit()
        db_session.refresh(user)
        return user
    return _make


@pytest.fixture()
def normal_user(make_user):
    return make_user(email="cliente@example.com")


@pytest.fixture()
def admin_user(make_user):
    return make_user(email="admin@example.com", is_admin=True)


@pytest.fixture()
def user_token(normal_user):
    return create_access_token(data={"sub": str(normal_user.id)})


@pytest.fixture()
def admin_token(admin_user):
    return create_access_token(data={"sub": str(admin_user.id)})


@pytest.fixture()
def auth_headers(user_token):
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture()
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture()
def sample_category(db_session):
    # Deliberately not one of routes.categories.DEFAULT_CATEGORIES' slugs: deleting
    # the last active category whose slug collides with a default triggers a real
    # reseed bug there (IntegrityError on the default's PK) - see test_categories.py.
    cat = Category(slug="categoria-test", name="Categoria de prueba", order_index=0)
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)
    return cat


@pytest.fixture()
def sample_product(db_session, sample_category):
    product = Product(
        name="Olla de acero 5L",
        description="Olla de acero inoxidable 304",
        price=49.99,
        stock=10,
        category=sample_category.slug,
        is_active=True,
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


def add_to_cart(db_session, user, product, quantity=2):
    cart = db_session.query(Cart).filter(Cart.user_id == user.id).first()
    item = CartItem(cart_id=cart.id, product_id=product.id, quantity=quantity)
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item


@pytest.fixture()
def cart_item(db_session, normal_user, sample_product):
    return add_to_cart(db_session, normal_user, sample_product, quantity=2)
