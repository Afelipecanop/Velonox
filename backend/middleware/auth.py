from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import logging

from database import get_db
from models.user import User
from services.auth import decode_token
from main import get_client_ip

logger = logging.getLogger(__name__)

# Extrae el token del header Authorization: Bearer <token>
security = HTTPBearer()


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Valida el token JWT y devuelve el usuario actual."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido o expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token_data = decode_token(credentials.credentials)
    if token_data is None:
        logger.warning(
            f"Token inválido/expirado (token='{credentials.credentials[:10]}...') "
            f"desde IP={get_client_ip(request)}"
        )
        raise credentials_exception

    user = db.query(User).filter(User.id == token_data.user_id).first()
    if user is None:
        logger.warning(
            f"Token válido pero usuario inexistente (user_id={token_data.user_id}) "
            f"desde IP={get_client_ip(request)}"
        )
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario desactivado"
        )
    return user


def get_current_admin(request: Request, current_user: User = Depends(get_current_user)) -> User:
    """Verifica que el usuario actual sea administrador."""
    if not current_user.is_admin:
        logger.warning(
            f"Acceso admin rechazado para user_id={current_user.id} "
            f"email='{current_user.email}' desde IP={get_client_ip(request)}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos de administrador"
        )
    return current_user