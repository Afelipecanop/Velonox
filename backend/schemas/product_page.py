from pydantic import BaseModel
from uuid import UUID
from typing import Any, Dict, List, Optional


class ProductSpec(BaseModel):
    key: str
    value: str


class ProductFeature(BaseModel):
    icon: str
    title: str
    text: str


class ProductPageUpdate(BaseModel):
    use_custom_layout: Optional[bool] = False
    description: Optional[str] = None
    specs: Optional[List[ProductSpec]] = None
    features: Optional[List[ProductFeature]] = None
    custom_blocks: Optional[List[Dict[str, Any]]] = None
    category: Optional[str] = None


class ProductPageResponse(BaseModel):
    product_id: UUID
    use_custom_layout: bool
    description: Optional[str] = None
    specs: Optional[List[ProductSpec]] = None
    features: Optional[List[ProductFeature]] = None
    custom_blocks: Optional[List[Dict[str, Any]]] = None
    category: Optional[str] = None
    class Config:
        from_attributes = True

        