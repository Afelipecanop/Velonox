from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import List, Optional
import secrets
import string

from database import get_db
from models.order import Order, OrderItem
from models.product import Product
from models.user import User
from services.auth import hash_password
from services.email import email_bienvenida
from services.bold import generate_integrity_signature, usd_to_cop
from services.settings import get_current_trm
from services.dropi import create_dropi_order
from main import limiter
import os
import logging

router = APIRouter(prefix="/guest", tags=["Checkout invitado"])
logger = logging.getLogger("velonox.guest_checkout")

BOLD_API_KEY = os.getenv("BOLD_API_KEY")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:5500")


class CartItemInput(BaseModel):
    product_id: str
    quantity: int


class ShippingAddress(BaseModel):
    direccion: str
    ciudad: str
    departamento: str
    codigo_postal: Optional[str] = None
    telefono: Optional[str] = None
    indicaciones: Optional[str] = None


class GuestCheckoutRequest(BaseModel):
    email: EmailStr
    nombre: str
    document_type: Optional[str] = None
    document_number: Optional[str] = None
    payment_method: str  # "anticipado" | "contraentrega"
    shipping_address: ShippingAddress
    items: List[CartItemInput]


def generate_temp_password(length: int = 10) -> str:
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))


@router.post("/checkout")
@limiter.limit("5/minute")
async def guest_checkout(
    request: Request,
    data: GuestCheckoutRequest,
    db: Session = Depends(get_db)
):
    if not data.items:
        raise HTTPException(status_code=400, detail="El carrito está vacío")

    # ── 1. Verificar productos y calcular total (NO descontar stock aún) ───────
    order_items_data = []
    total = 0.0

    for item in data.items:
        product = db.query(Product).filter(
            Product.id == item.product_id,
            Product.is_active == True
        ).first()

        if not product:
            raise HTTPException(404, f"Producto no encontrado: {item.product_id}")
        if product.stock < item.quantity:
            raise HTTPException(
                400, f"Stock insuficiente para '{product.name}'. Disponible: {product.stock}"
            )

        subtotal = product.price * item.quantity
        total += subtotal
        order_items_data.append({"product": product, "quantity": item.quantity})

    # ── 2. Buscar o crear usuario ────────────────────────────────────────────
    # RIESGO DE SEGURIDAD CONOCIDO (no corregido a propósito, ver auditoría de
    # agosto 2026): si el email ya corresponde a una cuenta existente, esta orden
    # se asocia igual a ese user_id real sin verificar que quien hace el checkout
    # sea el dueño del correo — cualquiera puede "ensuciar" el historial de
    # pedidos de una cuenta ajena. La corrección obvia es dejar `user_id` en NULL
    # en ese caso (la columna orders.user_id es nullable en models/order.py), pero
    # la tabla real en Postgres todavía tiene esa columna como NOT NULL desde la
    # migración inicial (ff0162fd9e2e_crear_tablas_iniciales.py) — nunca se migró
    # a nullable pese a que el modelo ya lo declara así. Poner NULL aquí revienta
    # con IntegrityError contra la DB real (confirmado manualmente). Corregirlo
    # requiere una migración de Alembic (`ALTER COLUMN user_id DROP NOT NULL`),
    # que no se generó ni se aplicó a propósito — pendiente de decisión.
    user = db.query(User).filter(User.email == data.email).first()
    cuenta_nueva = False
    temp_password = None

    if not user:
        temp_password = generate_temp_password()
        user = User(
            email=data.email,
            full_name=data.nombre,
            hashed_password=hash_password(temp_password),
            is_active=True,
            is_admin=False
        )
        db.add(user)
        db.flush()
        cuenta_nueva = True

    # ── 3. Crear la orden — mismos campos estructurados que el checkout logueado ─
    order = Order(
        user_id=user.id,
        status="pending",
        total_amount=total,
        payment_method=data.payment_method,
        guest_email=data.email,
        guest_name=data.nombre,
        document_type=data.document_type,
        document_number=data.document_number,
        customer_phone=data.shipping_address.telefono,
        shipping_address=data.shipping_address.direccion,
        shipping_notes=data.shipping_address.indicaciones,
        department_name=data.shipping_address.departamento,
        city_name=data.shipping_address.ciudad,
    )
    db.add(order)
    db.flush()

    for item_data in order_items_data:
        db.add(OrderItem(
            order_id=order.id,
            product_id=item_data["product"].id,
            quantity=item_data["quantity"],
            unit_price=item_data["product"].price
        ))
        # Stock NO se descuenta aquí para 'anticipado' — se descuenta en el webhook
        # de Bold cuando el pago se confirma. Para 'contraentrega' sí se descuenta ya,
        # porque el pedido queda confirmado de inmediato.
        if data.payment_method == "contraentrega":
            item_data["product"].stock -= item_data["quantity"]

    db.commit()
    db.refresh(order)

    nombre_corto = data.nombre.split()[0]
    if cuenta_nueva and temp_password:
        email_bienvenida(data.email, nombre_corto, temp_password)

    # ── 4a. Flujo Bold (anticipado): devolver datos para el botón ──────────────
    if data.payment_method == "anticipado":
        trm = get_current_trm(db)
        order.bold_order_id = f"VLX-{str(order.id)[:8]}-{int(order.total_amount)}"
        db.commit()

        amount_cop = usd_to_cop(order.total_amount, trm)
        signature = generate_integrity_signature(order.bold_order_id, amount_cop, "COP")

        return {
            "flow": "bold",
            "order_id": str(order.id),
            "bold_order_id": order.bold_order_id,
            "amount": amount_cop,
            "currency": "COP",
            "api_key": BOLD_API_KEY,
            "signature": signature,
            "redirection_url": f"{FRONTEND_URL}/pedido-confirmado.html?order_id={order.id}",
        }

    # ── 4b. Flujo contraentrega: confirmar ya, enviar a Dropi, enviar email ─────
    order.status = "cod_confirmed"
    try:
        dropi_response = create_dropi_order(order, order.items, is_cod=True)
        order.dropi_order_id = dropi_response.get("id")
        order.dropi_status = "created"
    except Exception as e:
        logger.error(f"Dropi falló para orden invitado {order.id}: {e}")
        order.dropi_status = "pending_manual"
    db.commit()

    from services.email import email_confirmacion_orden
    email_confirmacion_orden(
        to=data.email,
        nombre=nombre_corto,
        order_id=str(order.id),
        items=[{"product": i["product"], "quantity": i["quantity"],
                "unit_price": i["product"].price, "name": i["product"].name}
               for i in order_items_data],
        total=total,
        metodo=data.payment_method
    )

    return {
        "order_id": str(order.id),
        "flow": "cod",
        "total": total,
        "payment_method": data.payment_method,
        "mensaje": "Pedido creado exitosamente"
    }