from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from database import engine
from dotenv import load_dotenv
import os

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware

load_dotenv()


def get_client_ip(request: Request) -> str:
    """Devuelve la IP real del cliente. Railway corre la app detrás de un
    proxy, así que la IP de conexión (get_remote_address) es la del proxy,
    no la del cliente — hay que leerla de X-Forwarded-For."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=get_client_ip)

# Primero se crea app, LUEGO se usa
app = FastAPI(
    title="Mi E-commerce API",
    description="Backend de la tienda online",
    version="1.0.0"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:5500")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "https://e-commerce-con-fastapi-y-postgreqsl-production.up.railway.app",
        "https://e-commerce-con-fastapi-y-postgreqsl.pages.dev",
        "https://velonox.co",
        "https://www.velonox.co",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.add_middleware(SlowAPIMiddleware)

# Los routers se importan aquí (y no arriba con el resto de imports) porque
# algunos de ellos hacen "from main import limiter" para poder decorar sus
# endpoints con @limiter.limit(...) — para eso `limiter` ya debe existir en
# este módulo cuando Python los importe.
from routes.auth import router as auth_router
from routes.products import router as products_router
from routes.product_variants import router as product_variants_router
from routes.product_images import router as product_images_router
from routes.cart import router as cart_router
from routes.payments import router as payments_router
from routes.layout import router as layout_router
from routes.product_pages import router as product_pages_router
from routes.metrics import router as metrics_router
from routes.categories import router as categories_router
from routes.guest_checkout import router as guest_router
from routes.settings import router as settings_router

# Rutas
app.include_router(product_pages_router)
app.include_router(layout_router)
app.include_router(auth_router)
app.include_router(products_router)
app.include_router(product_variants_router)
app.include_router(product_images_router)
app.include_router(cart_router)
app.include_router(payments_router)
app.include_router(metrics_router)
app.include_router(categories_router)
app.include_router(guest_router)
app.include_router(settings_router)


@app.get("/")
def root():
    return {"mensaje": "API funcionando ✅"}


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/db-check")
def db_check():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"database": "conectada ✅"}
    except Exception:
        return {"database": "error ❌"}
    
