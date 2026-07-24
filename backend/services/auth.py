from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
import os

from models.user import User
from schemas.user import TokenData
import secrets
import hashlib
from models.password_reset_token import PasswordResetToken

RESET_TOKEN_EXPIRE_MINUTES = 30

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

# Configuración del hash de contraseñas con bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Convierte una contraseña en texto plano a un hash seguro."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica que una contraseña coincide con su hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Crea un token JWT con los datos del usuario y tiempo de expiración."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Busca un usuario en la base de datos por su email."""
    return db.query(User).filter(User.email == email).first()


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """Verifica email y contraseña. Devuelve el usuario si son correctos."""
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def verify_google_token(token: str) -> dict:
    """Verifica un ID token de Google Identity Services contra GOOGLE_CLIENT_ID.

    Lanza ValueError si el token es inválido, expiró o fue emitido para otro client_id.
    """
    return google_id_token.verify_oauth2_token(
        token, google_requests.Request(), GOOGLE_CLIENT_ID
    )


def get_or_create_google_user(db: Session, email: str, full_name: str) -> User:
    """Busca un usuario por email; si no existe, lo crea como usuario de Google."""
    user = get_user_by_email(db, email)
    if user:
        return user

    from models.cart import Cart

    user = User(
        email=email,
        hashed_password=None,
        full_name=full_name or email.split("@")[0],
        auth_provider="google",
    )
    db.add(user)
    db.flush()

    cart = Cart(user_id=user.id)
    db.add(cart)
    db.commit()
    db.refresh(user)
    return user


def decode_token(token: str) -> Optional[TokenData]:
    """Decodifica un JWT y devuelve los datos que contiene."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        return TokenData(user_id=user_id)
    except JWTError:
        return None

# Password reset token management

def _hash_reset_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def create_password_reset_token(db: Session, user: User) -> str:
    """Genera un token de recuperación, guarda solo su hash, y devuelve el token en texto plano (para el email)."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_reset_token(raw_token)

    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES),
    )
    db.add(reset_token)
    db.commit()

    return raw_token


def get_valid_reset_token(db: Session, raw_token: str) -> Optional[PasswordResetToken]:
    token_hash = _hash_reset_token(raw_token)
    reset_token = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == token_hash)
        .first()
    )
    if not reset_token:
        return None
    if reset_token.used:
        return None
    if reset_token.expires_at < datetime.now(timezone.utc):
        return None
    return reset_token


def consume_reset_token(db: Session, reset_token: PasswordResetToken, new_password: str):
    user = db.query(User).filter(User.id == reset_token.user_id).first()
    user.hashed_password = hash_password(new_password)
    reset_token.used = True
    db.commit()