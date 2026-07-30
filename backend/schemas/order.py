from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import List, Optional
from .product import ProductResponse
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from enum import Enum


class OrderItemResponse(BaseModel):
    id: UUID
    product: ProductResponse
    quantity: int
    unit_price: float

    class Config:
        from_attributes = True


class OrderResponse(BaseModel):
    id: UUID
    status: str
    total_amount: float
    stripe_payment_id: Optional[str]
    created_at: datetime
    items: List[OrderItemResponse]

    class Config:
        from_attributes = True


class CheckoutResponse(BaseModel):
    checkout_url: str
    order_id: str


class PaymentMethod(str, Enum):
    anticipado = "anticipado"
    contraentrega = "contraentrega"

class CheckoutRequest(BaseModel):
    customer_phone: str
    document_type: Optional[str] = None
    document_number: Optional[str] = None
    shipping_address: str
    shipping_notes: Optional[str] = None
    department_name: str
    city_name: str
    payment_method: PaymentMethod


class OrderStatusUpdate(BaseModel):
    status: str