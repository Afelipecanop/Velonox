from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta

from database import get_db
from models.user import User
from models.cart import Cart
from schemas.user import UserCreate, UserLogin, UserResponse, Token, GoogleAuth
from services.auth import (
    hash_password,
    authenticate_user,
    create_access_token,
    get_user_by_email,
    verify_google_token,
    get_or_create_google_user,
)
from middleware.auth import get_current_user
from schemas.user import ForgotPasswordRequest, ResetPasswordRequest
from services.auth import create_password_reset_token, get_valid_reset_token, consume_reset_token
from services.email import email_recuperacion_password
import os

FRONTEND_URL = os.getenv("FRONTEND_URL", "https://velonox.co")

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Registra un nuevo usuario y crea su carrito automáticamente."""

    # Verifica que el email no esté ya registrado
    if get_user_by_email(db, user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este email ya está registrado"
        )

    # Crea el usuario con la contraseña hasheada
    new_user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name,
    )
    db.add(new_user)
    db.flush()  # Obtiene el ID del usuario sin hacer commit aún

    # Crea el carrito vacío automáticamente para el nuevo usuario
    cart = Cart(user_id=new_user.id)
    db.add(cart)
    db.commit()
    db.refresh(new_user)

    return new_user


@router.post("/login", response_model=Token)
def login(user_data: UserLogin, db: Session = Depends(get_db)):
    """Autentica al usuario y devuelve un token JWT."""

    user = authenticate_user(db, user_data.email, user_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Crea el token con el ID del usuario
    access_token = create_access_token(data={"sub": str(user.id)})

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/google", response_model=Token)
def google_login(auth_data: GoogleAuth, db: Session = Depends(get_db)):
    """Autentica con un ID token de Google Identity Services y devuelve un token JWT."""

    try:
        payload = verify_google_token(auth_data.id_token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de Google inválido o expirado",
        )

    email = payload.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token de Google no incluye un email",
        )

    full_name = payload.get("name", "")
    user = get_or_create_google_user(db, email, full_name)

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario desactivado"
        )

    access_token = create_access_token(data={"sub": str(user.id)})

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Devuelve los datos del usuario autenticado."""
    return current_user


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
def forgot_password(data: ForgotPasswordRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Genera un token de recuperación y envía el email, si el usuario existe.

    Siempre responde con el mismo mensaje genérico, exista o no la cuenta,
    para no revelar qué correos están registrados. El envío del email corre
    en background para que el SMTP (lento o caído) nunca bloquee la respuesta.
    """
    user = get_user_by_email(db, data.email)
    if user and user.auth_provider == "local":
        raw_token = create_password_reset_token(db, user)
        reset_link = f"{FRONTEND_URL}/reset-password.html?token={raw_token}"
        background_tasks.add_task(email_recuperacion_password, user.email, user.full_name, reset_link)

    return {"message": "Si el correo está registrado, enviamos instrucciones para restablecer tu contraseña."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    reset_token = get_valid_reset_token(db, data.token)
    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El link de recuperación es inválido o expiró. Solicita uno nuevo.",
        )

    consume_reset_token(db, reset_token, data.new_password)
    return {"message": "Tu contraseña fue actualizada correctamente."}