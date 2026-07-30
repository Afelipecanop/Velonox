from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import logging
from dotenv import load_dotenv

from database import get_db
from models.cart import Cart, CartItem
from models.order import Order, OrderItem
from models.product import Product
from schemas.order import OrderResponse, CheckoutRequest, OrderStatusUpdate
from middleware.auth import get_current_user, get_current_admin
from services.bold import generate_integrity_signature, verify_webhook_signature, usd_to_cop
from services.email import email_confirmacion_orden
from services.dropi import create_dropi_order
from services.settings import get_current_trm

# Estados válidos para el flujo manual de pedidos (sin integración activa de Dropi)
ORDER_STATUSES = ["pending", "paid", "cod_confirmed", "shipped", "delivered", "cancelled"]

load_dotenv()

BOLD_API_KEY = os.getenv("BOLD_API_KEY")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:5500")

router = APIRouter(prefix="/payments", tags=["Pagos"])
logger = logging.getLogger("velonox.payments")


@router.post("/checkout")
def create_checkout(
    data: CheckoutRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Convierte el carrito en una orden. Según payment_method:
    - 'anticipado': crea la orden pending y devuelve los datos para el botón Bold.
    - 'contraentrega': confirma la orden de una vez y la envía a Dropi.
    """

    # 1. Obtener el carrito del usuario
    cart = db.query(Cart).filter(Cart.user_id == current_user.id).first()
    if not cart or not cart.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El carrito está vacío"
        )

    # 2. Verificar stock de todos los productos antes de procesar
    for item in cart.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if product.stock < item.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stock insuficiente para '{product.name}'. Disponible: {product.stock}"
            )

    # 3. Calcular el total
    total = sum(item.product.price * item.quantity for item in cart.items)

    # 4. Crear la orden en la DB con status 'pending'
    order = Order(
        user_id=current_user.id,
        status="pending",
        total_amount=total,
        customer_phone=data.customer_phone,
        document_type=data.document_type,
        document_number=data.document_number,
        shipping_address=data.shipping_address,
        shipping_notes=data.shipping_notes,
        department_name=data.department_name,
        city_name=data.city_name,
        payment_method=data.payment_method.value,
    )
    db.add(order)
    db.flush()

    # 5. Crear los items de la orden
    for item in cart.items:
        order_item = OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            quantity=item.quantity,
            unit_price=item.product.price
        )
        db.add(order_item)

    db.commit()
    db.refresh(order)

    # 6a. Flujo Bold (pago anticipado)
    if data.payment_method == "anticipado":
        order.bold_order_id = f"VLX-{str(order.id)[:8]}-{int(order.total_amount)}"
        db.commit()

        trm = get_current_trm(db)
        amount = usd_to_cop(order.total_amount, trm)
        signature = generate_integrity_signature(order.bold_order_id, amount, "COP")

        return {
            "flow": "bold",
            "order_id": str(order.id),
            "bold_order_id": order.bold_order_id,
            "amount": amount,
            "currency": "COP",
            "api_key": BOLD_API_KEY,
            "signature": signature,
            "redirection_url": f"{FRONTEND_URL}/pedido-confirmado.html?order_id={order.id}",
        }

    # 6b. Flujo contraentrega: confirma ya mismo y descuenta stock
    order.status = "cod_confirmed"
    for item in cart.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        product.stock = max(0, product.stock - item.quantity)

    for cart_item in cart.items:
        db.delete(cart_item)

    try:
        dropi_response = create_dropi_order(order, order.items, is_cod=True)
        order.dropi_order_id = dropi_response.get("id")
        order.dropi_status = "created"
    except Exception as e:
        logger.error(f"Dropi falló para orden {order.id}: {e}")
        order.dropi_status = "pending_manual"

    db.commit()
    return {"flow": "cod", "order_id": str(order.id), "status": "confirmado"}


# Payload real de Bold confirmado contra un evento de producción (2026-07-30):
# formato tipo CloudEvents, NO el que se había asumido originalmente ("data.payment.*").
#   {
#     "type": "SALE_REJECTED",              <- el estado va acá, a nivel raíz
#     "data": {
#       "metadata": {"reference": "VLX-..."}, <- nuestro bold_order_id va acá
#       "bold_code": "B010",
#       ...
#     }
#   }
# Solo se confirmó "SALE_REJECTED" con un pago real fallido; el nombre exacto del
# tipo para pagos aprobados no se ha visto todavía, así que el matching es por
# substring ("APPROVED" / "REJECTED" etc.) en vez de comparar el string completo,
# para no volver a romperse si Bold usa "SALE_APPROVED", "PAYMENT_APPROVED", etc.
BOLD_APPROVED_KEYWORDS = ("APPROVED",)
BOLD_REJECTED_KEYWORDS = ("REJECTED", "FAILED", "DECLINED", "VOIDED", "CANCELLED", "ERROR")


@router.post("/bold/webhook")
async def bold_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Bold llama a este endpoint cuando confirma un pago.
    Verifica la firma, marca la orden como pagada, descuenta stock,
    vacía el carrito y crea la orden en Dropi.
    """
    raw_body = await request.body()
    signature = request.headers.get("x-bold-signature", "")

    if not verify_webhook_signature(raw_body, signature):
        logger.warning(
            f"Webhook de Bold rechazado por firma inválida. Header recibido: '{signature}'. "
            f"Body: {raw_body[:500]!r}"
        )
        raise HTTPException(status_code=400, detail="Firma inválida")

    payload = await request.json()
    logger.info(f"Webhook de Bold recibido: {payload}")

    data = payload.get("data") or {}
    raw_type = payload.get("type")
    event_type = (raw_type or "").strip().upper()
    bold_order_id = (data.get("metadata") or {}).get("reference")
    bold_code = data.get("bold_code")

    if not bold_order_id:
        logger.warning(f"Webhook de Bold sin data.metadata.reference en el payload: {payload}")
        return {"status": "ignored"}

    order = db.query(Order).filter(Order.bold_order_id == bold_order_id).first()
    if not order:
        logger.warning(f"Webhook de Bold: no se encontró orden con bold_order_id={bold_order_id}")
        return {"status": "order not found"}

    is_approved = any(k in event_type for k in BOLD_APPROVED_KEYWORDS)
    is_rejected = any(k in event_type for k in BOLD_REJECTED_KEYWORDS)

    if is_approved and order.status == "pending":
        order.status = "paid"
        db.commit()

        for item in order.items:
            product = db.query(Product).filter(Product.id == item.product_id).first()
            if product:
                product.stock = max(0, product.stock - item.quantity)
        db.commit()

        cart = db.query(Cart).filter(Cart.user_id == order.user_id).first()
        if cart:
            for cart_item in cart.items:
                db.delete(cart_item)
            db.commit()

        try:
            dropi_response = create_dropi_order(order, order.items, is_cod=False)
            order.dropi_order_id = dropi_response.get("id")
            order.dropi_status = "created"
        except Exception as e:
            logger.error(f"Dropi falló para orden {order.id}: {e}")
            order.dropi_status = "pending_manual"
        db.commit()

        # Enviar email de confirmación (funciona igual para usuario logueado o invitado)
        try:
            recipient_email = order.guest_email or (order.user.email if order.user else None)
            recipient_name = order.guest_name or (order.user.full_name if order.user else "Cliente")
            if recipient_email:
                email_confirmacion_orden(
                    to=recipient_email,
                    nombre=recipient_name.split()[0],
                    order_id=str(order.id),
                    items=[{"product": i.product, "quantity": i.quantity,
                            "unit_price": i.unit_price, "name": i.product.name}
                            for i in order.items],
                    total=order.total_amount,
                    metodo="anticipado"
                )
        except Exception as e:
            logger.error(f"Email de confirmación falló para orden {order.id}: {e}")

    elif is_rejected and order.status == "pending":
        order.status = "cancelled"
        db.commit()
        logger.info(
            f"Orden {order.id} cancelada por Bold (type recibido: '{raw_type}', bold_code: {bold_code})"
        )

    elif order.status != "pending":
        logger.info(
            f"Webhook de Bold ignorado para orden {order.id}: ya estaba en estado "
            f"'{order.status}' (type recibido: '{raw_type}')"
        )
    else:
        logger.warning(
            f"Webhook de Bold con type desconocido '{raw_type}' para orden {order.id}. "
            f"No se procesó ningún cambio de estado."
        )

    return {"status": "ok"}


@router.get("/orders", response_model=List[OrderResponse])
def get_my_orders(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Devuelve el historial de órdenes del usuario autenticado."""
    orders = db.query(Order).filter(
        Order.user_id == current_user.id
    ).order_by(Order.created_at.desc()).all()
    return orders


@router.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Devuelve el detalle de una orden específica del usuario."""
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.user_id == current_user.id
    ).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Orden no encontrada"
        )
    return order


@router.get("/admin/orders")
def get_all_orders_admin(
    status_filter: Optional[str] = None,
    payment_method: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin)
):
    """Lista TODOS los pedidos de la tienda (no solo los recientes). Solo administradores."""
    query = db.query(Order)
    if status_filter:
        query = query.filter(Order.status == status_filter)
    if payment_method:
        query = query.filter(Order.payment_method == payment_method)

    orders = query.order_by(Order.created_at.desc()).all()

    result = []
    for o in orders:
        customer_name = o.guest_name or (o.user.full_name if o.user else "—")
        customer_email = o.guest_email or (o.user.email if o.user else "—")

        if search:
            s = search.lower()
            haystack = f"{customer_name} {customer_email} {o.id}".lower()
            if s not in haystack:
                continue

        result.append({
            "id": str(o.id),
            "status": o.status,
            "payment_method": o.payment_method,
            "total_amount": float(o.total_amount),
            "dropi_status": o.dropi_status,
            "dropi_order_id": o.dropi_order_id,
            "bold_order_id": o.bold_order_id,
            "customer_name": customer_name,
            "customer_email": customer_email,
            "customer_phone": o.customer_phone,
            "shipping_address": o.shipping_address,
            "shipping_notes": o.shipping_notes,
            "department_name": o.department_name,
            "city_name": o.city_name,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "items": [
                {
                    "product_name": i.product.name if i.product else "—",
                    "quantity": i.quantity,
                    "unit_price": float(i.unit_price),
                }
                for i in o.items
            ],
        })

    return result


@router.patch("/admin/orders/{order_id}")
def update_order_status_admin(
    order_id: str,
    data: OrderStatusUpdate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin)
):
    """
    Cambia el estado de un pedido manualmente (flujo manual mientras no haya
    integración de Dropi para contraentrega). Si se confirma manualmente el pago
    de un pedido 'anticipado' que seguía pending (ej. el webhook de Bold no llegó),
    replica el mismo efecto que el webhook: descuenta stock, vacía el carrito y
    crea la orden en Dropi.
    """
    if data.status not in ORDER_STATUSES:
        raise HTTPException(status_code=400, detail="Estado inválido")

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    previous_status = order.status

    if (
        data.status == "paid"
        and previous_status == "pending"
        and order.payment_method == "anticipado"
    ):
        for item in order.items:
            product = db.query(Product).filter(Product.id == item.product_id).first()
            if product:
                product.stock = max(0, product.stock - item.quantity)

        cart = db.query(Cart).filter(Cart.user_id == order.user_id).first()
        if cart:
            for cart_item in cart.items:
                db.delete(cart_item)

        try:
            dropi_response = create_dropi_order(order, order.items, is_cod=False)
            order.dropi_order_id = dropi_response.get("id")
            order.dropi_status = "created"
        except Exception as e:
            logger.error(f"Dropi falló para orden {order.id}: {e}")
            order.dropi_status = "pending_manual"

        try:
            recipient_email = order.guest_email or (order.user.email if order.user else None)
            recipient_name = order.guest_name or (order.user.full_name if order.user else "Cliente")
            if recipient_email:
                email_confirmacion_orden(
                    to=recipient_email,
                    nombre=recipient_name.split()[0],
                    order_id=str(order.id),
                    items=[{"product": i.product, "quantity": i.quantity,
                            "unit_price": i.unit_price, "name": i.product.name}
                            for i in order.items],
                    total=order.total_amount,
                    metodo="anticipado"
                )
        except Exception as e:
            logger.error(f"Email de confirmación falló para orden {order.id}: {e}")

    order.status = data.status
    db.commit()
    db.refresh(order)
    return {"id": str(order.id), "status": order.status}