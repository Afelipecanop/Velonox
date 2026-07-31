from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
import json

from database import get_db
from models.product import Product
from models.product_page import ProductPage
from schemas.product_page import ProductPageUpdate, ProductPageResponse
from middleware.auth import get_current_admin

router = APIRouter(prefix="/product-pages", tags=["Páginas de producto"])

# Specs por defecto para productos Velonox
DEFAULT_SPECS = [
    {"key": "Material", "value": "Acero inoxidable 304"},
    {"key": "Compatible inducción", "value": "Sí"},
    {"key": "Apto horno", "value": "Hasta 220°C"},
    {"key": "Apto lavavajillas", "value": "Sí"},
    {"key": "Garantía", "value": "1 año"},
]

DEFAULT_FEATURES = [
    {"icon": "🔥", "title": "Calor uniforme", "text": "El núcleo de aluminio distribuye el calor de forma homogénea, eliminando puntos fríos y quemados."},
    {"icon": "⚡", "title": "Apta para inducción", "text": "Compatible con todas las fuentes de calor: inducción, vitrocerámica, gas y horno convencional."},
    {"icon": "🛡️", "title": "Sin tóxicos", "text": "Acero 304 completamente inerte. Sin PFAS, sin PTFE, sin níquel libre. Seguro para toda la familia."},
    {"icon": "♾️", "title": "Vida útil 25+ años", "text": "Con el cuidado correcto, una olla Velonox dura décadas. Invertir una vez, cocinar toda la vida."},
]


@router.get("/{product_id}", response_model=ProductPageResponse)
def get_product_page(product_id: UUID, db: Session = Depends(get_db)):
    """
    Devuelve la configuración de la página de un producto.
    Si no tiene configuración propia devuelve los defaults de Velonox.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    page = db.query(ProductPage).filter(
        ProductPage.product_id == product_id
    ).first()

    if not page:
        # Devuelve defaults sin crear nada en la DB
        return ProductPageResponse(
            product_id=product_id,
            use_custom_layout=False,
            description=product.description or "Producto de acero inoxidable grado 304. Calidad premium para el hogar latinoamericano.",
            specs=DEFAULT_SPECS,
            features=DEFAULT_FEATURES,
            custom_blocks=[]
        )

    return ProductPageResponse(
        product_id=product_id,
        use_custom_layout=page.use_custom_layout,
        description=page.description or product.description,
        specs=json.loads(page.specs) if page.specs else DEFAULT_SPECS,
        features=json.loads(page.features) if page.features else DEFAULT_FEATURES,
        custom_blocks=json.loads(page.custom_blocks) if page.custom_blocks else []
    )


@router.put("/{product_id}", response_model=ProductPageResponse)
def update_product_page(
    product_id: UUID,
    data: ProductPageUpdate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin)
):
    """
    Guarda o actualiza la configuración de la página de un producto.
    Solo administradores.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    page = db.query(ProductPage).filter(
        ProductPage.product_id == product_id
    ).first()

    if not page:
        page = ProductPage(product_id=product_id)
        db.add(page)

    if data.use_custom_layout is not None:
        page.use_custom_layout = data.use_custom_layout
    if data.description is not None:
        page.description = data.description
    if data.specs is not None:
        page.specs = json.dumps([s.model_dump() for s in data.specs])
    if data.features is not None:
        page.features = json.dumps([f.model_dump() for f in data.features])
    if data.custom_blocks is not None:
        page.custom_blocks = json.dumps(data.custom_blocks)

    db.commit()
    db.refresh(page)

    return ProductPageResponse(
        product_id=product_id,
        use_custom_layout=page.use_custom_layout,
        description=page.description,
        specs=json.loads(page.specs) if page.specs else DEFAULT_SPECS,
        features=json.loads(page.features) if page.features else DEFAULT_FEATURES,
        custom_blocks=json.loads(page.custom_blocks) if page.custom_blocks else []
    )


@router.delete("/{product_id}")
def reset_product_page(
    product_id: UUID,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin)
):
    """
    Elimina la configuración personalizada y vuelve a la plantilla base.
    Solo administradores.
    """
    page = db.query(ProductPage).filter(
        ProductPage.product_id == product_id
    ).first()
    if page:
        db.delete(page)
        db.commit()
    return {"mensaje": "Página restablecida a plantilla base ✅"}