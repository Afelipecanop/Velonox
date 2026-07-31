<div align="center">

# 🛍️ Velonox Store

**Plataforma de e-commerce full-stack construida con FastAPI, PostgreSQL y JavaScript vanilla**

Autenticación · Catálogo · Carrito · Checkout (registrado e invitado) · Pagos · Panel administrativo · CMS visual · Métricas de negocio

### 🔗 [velonox.co](https://velonox.co)

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.x-D71F00)](https://www.sqlalchemy.org/)
[![Alembic](https://img.shields.io/badge/Alembic-Migrations-6BA539)](https://alembic.sqlalchemy.org/)
[![Vanilla JS](https://img.shields.io/badge/Frontend-HTML%2FCSS%2FJS-F7DF1E?logo=javascript&logoColor=black)](#)
[![Railway](https://img.shields.io/badge/Backend-Railway-0B0D0E?logo=railway&logoColor=white)](https://railway.app/)
[![Cloudflare Pages](https://img.shields.io/badge/Frontend-Cloudflare%20Pages-F38020?logo=cloudflare&logoColor=white)](https://velonox.co)
[![License](https://img.shields.io/badge/status-en%20producción-brightgreen)](#)

</div>

---

## 📌 Tabla de contenidos

- [Sobre el proyecto](#-sobre-el-proyecto)
- [Estado actual](#-estado-actual)
- [Arquitectura](#-arquitectura)
- [Características](#-características)
- [Stack técnico](#-stack-técnico)
- [Estructura del proyecto](#-estructura-del-proyecto)
- [Instalación rápida](#-instalación-rápida)
- [Cómo correr los tests](#-cómo-correr-los-tests)
- [Variables de entorno](#-variables-de-entorno)
- [Despliegue](#-despliegue)
- [Mantenimiento continuo](#-mantenimiento-continuo)

---

##  Sobre el proyecto

**Velonox Store** es una tienda online construida desde cero con un enfoque comercial completo: no es solo un catálogo con carrito, sino una plataforma con panel administrativo, edición visual del layout, checkout invitado, integración con pasarelas de pago y fulfillment, y un sistema de moneda dinámico USD/COP.

El backend expone una API REST con **FastAPI** sobre **PostgreSQL** (SQLAlchemy 2.x, patrón síncrono), y el frontend es **HTML, CSS y JavaScript vanilla**, sin frameworks — priorizando control total y rendimiento sobre el "boilerplate" de un SPA.

##  Estado actual

**La tienda está finalizada y operando en producción**, vendiendo activamente en [velonox.co](https://velonox.co). Todos los módulos core están completos y estables:

| Módulo | Estado |
|---|---|
| Autenticación (JWT) | ✅ Operativo |
| Catálogo, productos y categorías | ✅ Operativo |
| Carrito y checkout (registrado / invitado) | ✅ Operativo |
| Pagos con Bold (webhooks + firma de integridad) | ✅ Operativo |
| Fulfillment con Dropi | ✅ Operativo |
| CMS visual del layout (con historial y restauración) | ✅ Operativo |
| Panel administrativo | ✅ Operativo |
| Métricas de negocio | ✅ Operativo |
| Conversión USD/COP vía TRM | ✅ Operativo |

De aquí en adelante, el trabajo sobre el repositorio consiste en **nuevas implementaciones puntuales y corrección de bugs** que se detecten en producción, no en desarrollo de funcionalidades base.

## 🏗️ Arquitectura

```mermaid
flowchart LR
    subgraph Cliente["🌐 Cliente"]
        FE["Frontend estático\nHTML / CSS / JS vanilla\n(Cloudflare Pages)"]
    end

    subgraph Servidor["⚙️ Backend — FastAPI (Railway)"]
        API["API REST"]
        AUTH["Auth · JWT"]
        CATALOG["Productos · Categorías · Layout CMS"]
        CART["Carrito · Checkout · Checkout invitado"]
        METRICS["Métricas de negocio"]
    end

    DB[(" PostgreSQL")]
    BOLD[" Bold\nPagos + Webhooks"]
    DROPI[" Dropi\nFulfillment"]
    TRM[" TRM\nUSD ⇄ COP"]
    AI[" IA\nGenerador de bloques visuales"]
    N8N[" n8n\nAsistente de chat"]

    FE -->|HTTPS / JSON| API
    API --> AUTH & CATALOG & CART & METRICS
    AUTH --> DB
    CATALOG --> DB
    CART --> DB
    METRICS --> DB
    CART -->|checkout| BOLD
    BOLD -->|webhook: pago confirmado| CART
    CART -->|crea guía de envío| DROPI
    CATALOG -->|conversión de precios| TRM
    CATALOG -->|generación de contenido| AI
    FE -->|widget de chat, directo| N8N
```

##  Características

<table>
<tr>
<td valign="top" width="50%">

### Frontend

- Home con catálogo destacado y contenido visual administrable
- Detalle de producto con descripción, specs, características y relacionados
- Carrito con actualización de cantidades y eliminación de ítems
- Checkout con dos modalidades: pago anticipado y contraentrega
- Checkout invitado sin registro previo
- Panel administrativo para layout, productos, categorías, marca y métricas
- Páginas institucionales, contacto, políticas, regalos y sets
- Widget de chat (asistente virtual) embebido en las páginas comerciales, conectado a un flujo de automatización en n8n

</td>
<td valign="top" width="50%">

### Backend

- API REST con FastAPI y autenticación JWT
- Gestión de usuarios, productos, categorías, carritos, órdenes y páginas de producto
- Integración con pagos y webhooks de Bold (firma de integridad + confirmación de estados)
- Creación automática de órdenes de envío en Dropi
- CMS de layout con bloques configurables, historial de versiones y restauración
- Endpoints de métricas de negocio, checkout invitado, TRM y ajustes de tienda
- Arquitectura preparada para nuevos servicios y funcionalidades

</td>
</tr>
</table>

##  Novedades recientes

> Con la tienda en producción, esta sección funciona como changelog: nuevas implementaciones y correcciones de bugs encontrados sobre la marcha.

- Integración de autenticación con Google Identity Services en la página de login, con endpoint backend para validar el token de Google y crear o reutilizar la cuenta del usuario.
- Flujo de acceso híbrido que soporta login con email/contraseña y login social, incluyendo la creación automática de carrito para usuarios que ingresan por Google.
- Mejoras en el panel administrativo con previsualización en vivo del layout y soporte para historial y restauración de versiones previas del CMS visual.
- Widget de chat propio (`frontend/js/velonox-chat-widget.js`) enlazado en las páginas comerciales (home, catálogo, categorías, producto, carrito, checkout, institucionales, regalos y sets), no en páginas de autenticación/confirmación/admin. Envía los mensajes directamente desde el navegador a un webhook de n8n que orquesta la lógica del asistente; mantiene la conversación por sesión de visitante vía `localStorage`.
- Nueva pestaña "Pedidos" en el panel administrativo: listado completo de órdenes (no solo las 8 más recientes de Métricas), con filtros por estado/método de pago/búsqueda, cambio manual de estado y un indicador visual de si el pago con Bold fue confirmado, pendiente o rechazado — necesario mientras no se cuenta con credenciales de Dropi para automatizar contraentrega. Cada pedido tiene un detalle expandible con dirección de envío, teléfono, tipo/número de documento, código DANE de la ciudad y referencias Bold/Dropi, para poder crear la guía de envío en Dropi manualmente.
- Corrección de bug real: el webhook de Bold no actualizaba el estado de los pedidos porque el payload real que envía Bold (formato tipo CloudEvents, con el estado en `type` y la referencia en `data.metadata.reference`) no coincidía con la estructura que asumía el backend; se corrigió el parseo.
- Corrección de bug real: CORS no incluía el método `PATCH`, lo que rompía con un 400 en preflight el cambio de estado de pedidos desde el admin.

##  Stack técnico

| Categoría | Tecnología |
|---|---|
| **Lenguaje** | Python 3.10+ |
| **Framework backend** | FastAPI + Uvicorn |
| **ORM / Base de datos** | SQLAlchemy 2.x (síncrono) + PostgreSQL |
| **Migraciones** | Alembic |
| **Frontend** | HTML5, CSS3, JavaScript vanilla |
| **Pagos** | Bold |
| **Fulfillment** | Dropi |
| **Contenido generativo** | API de IA para bloques visuales (server-side) |
| **Asistente de chat** | Widget propio (`js/velonox-chat-widget.js`) conectado a n8n |
| **Analítica** | Cloudflare Web Analytics |
| **Infraestructura** | Railway (backend) · Cloudflare Pages (frontend) |

## 📁 Estructura del proyecto

```
.
├── backend/          # Lógica del servidor
│   ├── routes/        # auth, products, categories, cart, payments,
│   │                   # guest_checkout, layout, product_pages, metrics, settings
│   ├── models/         # Modelos SQLAlchemy
│   ├── schemas/         # Esquemas Pydantic
│   ├── services/         # Integraciones (Bold, Dropi, TRM, IA)
│   ├── middleware/         # CORS y seguridad
│   └── alembic/              # Migraciones de base de datos
├── frontend/          # Páginas HTML, estilos y scripts del cliente
├── docs/              # Documentación técnica y de negocio
└── INFORME_PROYECTO.txt  # Documento de seguimiento del proyecto
```

##  Instalación rápida

```bash
# 1. Crear y activar entorno virtual
python -m venv venv
source venv/bin/activate      # En Windows: venv\Scripts\activate

# 2. Instalar dependencias del backend
pip install -r backend/requirements.txt

# 3. Configurar variables de entorno (ver sección siguiente)
cp .env.example .env

# 4. Ejecutar migraciones
cd backend
alembic upgrade head

# 5. Levantar la API
uvicorn main:app --reload

# 6. Servir el frontend
#    Abrir frontend/index.html o servirlo con un servidor estático local
```

## 🧪 Cómo correr los tests

El backend tiene una suite de pytest (`backend/tests/`) que corre contra una base de datos SQLite en memoria y nunca toca `DATABASE_URL` real ni servicios externos (Bold, Dropi, Resend, TRM y Google quedan mockeados o deshabilitados en el entorno de test).

```bash
cd backend
pip install -r requirements-dev.txt   # agrega pytest y pytest-cov sobre requirements.txt

pytest                     # correr toda la suite
pytest --cov=.             # con reporte de cobertura (usa backend/.coveragerc)
pytest --cov=. --cov-report=term-missing   # cobertura + líneas sin cubrir
pytest tests/test_payments.py -v           # un archivo puntual
```

## 🔐 Variables de entorno

| Variable | Propósito |
|---|---|
| `DATABASE_URL` | Cadena de conexión a PostgreSQL |
| `SECRET_KEY` | Firma de tokens JWT |
| `FRONTEND_URL` | Origen permitido para CORS |
| `BOLD_API_KEY` / `BOLD_SECRET_KEY` | Integración de pagos con Bold |
| `DROPI_BASE_URL` / `DROPI_API_KEY` | Integración de fulfillment con Dropi |
| `ANTHROPIC_API_KEY` | Generación de bloques visuales vía IA |
| `RESEND_API_KEY` / `EMAILS_FROM` | Envío de correos transaccionales vía Resend |

> No se incluyen credenciales ni secretos en este repositorio.

##  Despliegue

- **Backend** → Railway
- **Frontend** → Cloudflare Pages ([velonox.co](https://velonox.co))
- **Base de datos** → PostgreSQL gestionada por el entorno de ejecución del backend
- **Seguridad** → CORS y políticas de acceso configuradas explícitamente para permitir solo los orígenes esperados

## 🛠️ Mantenimiento continuo

La tienda ya está lista para vender. El trabajo futuro no es un roadmap hacia un "producto terminado", sino mantenimiento continuo sobre una plataforma ya en producción:

- Corrección de bugs reportados en producción
- Implementaciones puntuales solicitadas sobre módulos existentes
- Ajustes de UX/UI y contenido a medida que se detecten oportunidades
- Mejoras de rendimiento, seguridad y observabilidad cuando aplique

---

<div align="center">

Tienda finalizada y en producción en [velonox.co](https://velonox.co). A partir de aquí, este repositorio evoluciona mediante nuevas implementaciones y corrección de bugs.

</div>
