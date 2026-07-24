from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import json
import uuid
import httpx
import os
import requests as http_requests

from database import get_db
from models.layout import StoreLayout, StoreLayoutHistory
from schemas.layout import LayoutUpdate, BlockResponse, BlockConfig, AIGenerateRequest
from middleware.auth import get_current_admin

router = APIRouter(prefix="/layout", tags=["Layout de la tienda"])

# Cuántas versiones anteriores se conservan por página en el historial
MAX_HISTORY_PER_PAGE = 20


def _snapshot_current_layout(db: Session, page: str) -> None:
    """Guarda el estado actual de una página como una versión de historial antes de sobreescribirlo."""
    blocks = (
        db.query(StoreLayout)
        .filter(StoreLayout.page_slug == page)
        .order_by(StoreLayout.order_index)
        .all()
    )
    if not blocks:
        return

    snapshot = [
        {
            "id": b.id,
            "block_type": b.block_type,
            "order_index": b.order_index,
            "is_visible": b.is_visible,
            "config": json.loads(b.config),
        }
        for b in blocks
    ]
    db.add(StoreLayoutHistory(
        id=str(uuid.uuid4()),
        page_slug=page,
        blocks=json.dumps(snapshot),
    ))
    db.flush()

    # Poda versiones viejas, nos quedamos solo con las últimas MAX_HISTORY_PER_PAGE
    old_versions = (
        db.query(StoreLayoutHistory)
        .filter(StoreLayoutHistory.page_slug == page)
        .order_by(StoreLayoutHistory.created_at.desc())
        .offset(MAX_HISTORY_PER_PAGE)
        .all()
    )
    for old in old_versions:
        db.delete(old)


@router.post("/generate-block")
async def generate_block(
    request: dict,
    admin=Depends(get_current_admin)
):
    """Genera HTML/CSS con IA para un bloque personalizado."""
    prompt = request.get("prompt", "")
    
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if not anthropic_key:
        raise HTTPException(status_code=500, detail="Asistente IA no configurado")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": anthropic_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 1000,
                "messages": [{
                    "role": "user",
                    "content": f"""Eres un experto en HTML y CSS para e-commerce.
Genera una sección HTML/CSS profesional para una tienda online.

La sección debe:
- Tener diseño moderno y limpio
- Usar colores que combinen con azul (#2563eb) como color primario
- Ser responsive
- NO usar frameworks externos (solo HTML y CSS puro)

El usuario quiere: "{prompt}"

Responde SOLO con un objeto JSON con esta estructura exacta, sin explicaciones ni markdown:
{{"html": "el HTML completo aquí", "css": "el CSS adicional aquí"}}"""
                }]
            },
            timeout=30.0
        )
        
        data = response.json()
        text = data["content"][0]["text"]
        
        try:
            import json
            clean = text.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(clean)
        except:
            parsed = {"html": text, "css": ""}
            
        return parsed

# Bloques por defecto que tiene la tienda al inicio (diseño original de Velonox,
# no un placeholder genérico — ver renderLayoutBlock() en index.html para el HTML real).
DEFAULT_BLOCKS = [
    {
        "id": "block-banner",
        "block_type": "hero_banner",
        "order_index": 0,
        "is_visible": True,
        "config": {
            "title": "Cocina de",
            "subtitle": "por vida.",
            "button_text": "Ver productos",
            "image_url": "",
            "background_color": "#0F1A14",
            "text_color": "#ffffff"
        }
    },
    {
        "id": "block-products",
        "block_type": "product_grid",
        "order_index": 1,
        "is_visible": True,
        "config": {
            "title": "Nuestros productos",
            "columns": 3,
            "show_all": True,
            "limit": 6
        }
    },
    {
        "id": "block-why",
        "block_type": "custom_html",
        "order_index": 2,
        "is_visible": True,
        "config": {
            "css": "",
            "html": """<section style="background:#0F1A14;padding:3.5rem 2rem" id="why">
    <h2 style="font-family:'Playfair Display',serif;font-size:28px;font-weight:700;color:#C8D8C0;margin-bottom:2rem">¿Por qué acero inoxidable?</h2>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1px;background:#1A2820">
        <div style="background:#0F1A14;padding:1.5rem;display:flex;flex-direction:column;gap:.75rem">
            <p style="font-family:'Playfair Display',serif;font-size:36px;font-weight:900;color:#1D7A4F;line-height:1">0</p>
            <p style="font-size:14px;font-weight:500;color:#C8D8C0;line-height:1.4">Tóxicos liberados al cocinar</p>
            <p style="font-size:12px;color:#4A6A5A;line-height:1.6">El teflón libera PFAS a temperaturas comunes. El acero 304 es inerte: no reacciona con los alimentos.</p>
        </div>
        <div style="background:#0F1A14;padding:1.5rem;display:flex;flex-direction:column;gap:.75rem">
            <p style="font-family:'Playfair Display',serif;font-size:36px;font-weight:900;color:#1D7A4F;line-height:1">25+</p>
            <p style="font-size:14px;font-weight:500;color:#C8D8C0;line-height:1.4">Años de vida útil promedio</p>
            <p style="font-size:12px;color:#4A6A5A;line-height:1.6">Una buena sartén de acero dura décadas con uso correcto. El teflón: 2–5 años.</p>
        </div>
        <div style="background:#0F1A14;padding:1.5rem;display:flex;flex-direction:column;gap:.75rem">
            <p style="font-family:'Playfair Display',serif;font-size:36px;font-weight:900;color:#1D7A4F;line-height:1">100%</p>
            <p style="font-size:14px;font-weight:500;color:#C8D8C0;line-height:1.4">Compatible con inducción</p>
            <p style="font-size:12px;color:#4A6A5A;line-height:1.6">Funciona en todas las fuentes de calor: inducción, vitrocerámica, gas y horno.</p>
        </div>
        <div style="background:#0F1A14;padding:1.5rem;display:flex;flex-direction:column;gap:.75rem">
            <p style="font-family:'Playfair Display',serif;font-size:36px;font-weight:900;color:#1D7A4F;line-height:1">↑</p>
            <p style="font-size:14px;font-weight:500;color:#C8D8C0;line-height:1.4">Retención de calor superior</p>
            <p style="font-size:12px;color:#4A6A5A;line-height:1.6">El acero de triple capa distribuye el calor de forma uniforme, eliminando puntos quemados.</p>
        </div>
    </div>
</section>"""
        }
    },
    {
        "id": "block-footer",
        "block_type": "footer",
        "order_index": 3,
        "is_visible": True,
        "config": {
            "store_name": "Velonox",
            "tagline": "Cocina de por vida.",
            "email": "contacto@velonox.co",
            "background_color": "#0F1A14",
            "text_color": "#94a3b8"
        }
    }
]

# Bloques por defecto de las páginas de contenido (no la principal).
# Reproducen exactamente el diseño que ya tenían esas páginas como HTML
# estático, para que al activar el editor no cambie nada visualmente.
CONTENT_PAGE_BLOCKS = {
    "contacto": [
        {
            "block_type": "content_hero",
            "config": {
                "eyebrow": "Estamos aquí para ayudarte",
                "title_html": "Hablemos de <em>cocina.</em>",
                "text": "¿Tienes dudas sobre nuestros productos, tu pedido o quieres saber qué set es el ideal para tu cocina? Escríbenos."
            }
        },
        {
            "block_type": "custom_html",
            "config": {
                "css": "",
                "html": """<div class="main">
    <div class="contact-info">
        <div class="info-block">
            <p class="info-block-eyebrow">WhatsApp Business</p>
            <h3>Respuesta más rápida</h3>
            <p>Para consultas sobre productos, pedidos o asesoría personalizada. Respondemos en menos de 2 horas en horario hábil.</p>
            <a href="https://wa.me/573108887296?text=Hola%20Velonox%2C%20tengo%20una%20consulta%20sobre%20sus%20productos" target="_blank" class="whatsapp-btn">
                <i class="ti ti-brand-whatsapp"></i>
                <div><div>Escribir por WhatsApp</div><div class="whatsapp-sub">+57 310 888 7296</div></div>
            </a>
        </div>
        <div class="info-block">
            <p class="info-block-eyebrow">Horario de atención</p>
            <h3>Cuándo estamos disponibles</h3>
            <div class="horario-grid">
                <div class="horario-item"><strong>Lunes — Viernes</strong>8:00 am — 6:00 pm</div>
                <div class="horario-item"><strong>Sábados</strong>9:00 am — 1:00 pm</div>
            </div>
            <div class="tiempo-resp">
                <i class="ti ti-clock"></i>
                <span>Tiempo de respuesta: <strong>menos de 2 horas</strong></span>
            </div>
        </div>
        <div class="info-block">
            <p class="info-block-eyebrow">Ubicación</p>
            <h3>Colombia</h3>
            <p>Operamos desde Colombia con envíos a toda Latinoamérica. Próximamente con presencia en México, Perú y Chile.</p>
        </div>
    </div>
    <div class="contact-form">
        <p class="form-eyebrow">Formulario de contacto</p>
        <h2 class="form-title">¿En qué te podemos ayudar?</h2>
        <div id="form-alert" class="alert"></div>
        <div class="form-row">
            <div class="form-group"><label>Nombre</label><input type="text" id="f-name" placeholder="Tu nombre"></div>
            <div class="form-group"><label>Email</label><input type="email" id="f-email" placeholder="tu@email.com"></div>
        </div>
        <div class="form-group">
            <label>Motivo de contacto</label>
            <select id="f-motivo">
                <option value="">Selecciona un motivo</option>
                <option value="producto">Consulta sobre un producto</option>
                <option value="pedido">Estado de mi pedido</option>
                <option value="devolucion">Devolución o garantía</option>
                <option value="envio">Información de envíos</option>
                <option value="mayoreo">Compras al por mayor</option>
                <option value="otro">Otro</option>
            </select>
        </div>
        <div class="form-group"><label>Mensaje</label><textarea id="f-mensaje" placeholder="Cuéntanos en qué te podemos ayudar..."></textarea></div>
        <button class="btn-submit" id="btn-submit" onclick="handleSubmit()">
            <i class="ti ti-send"></i> Enviar mensaje
        </button>
        <p class="form-note">También puedes escribirnos directo por WhatsApp para una respuesta más rápida.</p>
    </div>
</div>
<section class="faq">
    <div class="faq-inner">
        <p class="faq-eyebrow">Preguntas frecuentes</p>
        <h2>Lo que más nos preguntan</h2>
        <div class="faq-item">
            <div class="faq-q" onclick="toggleFaq(this)">¿El acero inoxidable 304 es seguro para cocinar?<i class="ti ti-plus"></i></div>
            <div class="faq-a">Sí, completamente. El acero inoxidable 304 es el estándar de la industria alimentaria mundial. Es inerte — no reacciona con los alimentos, no libera químicos y no se degrada con el tiempo ni con el calor.</div>
        </div>
        <div class="faq-item">
            <div class="faq-q" onclick="toggleFaq(this)">¿Cuánto tiempo tarda el envío?<i class="ti ti-plus"></i></div>
            <div class="faq-a">En Colombia: 2 a 5 días hábiles. Para el resto de Latinoamérica: 7 a 15 días hábiles. Recibirás un número de seguimiento una vez despachado tu pedido.</div>
        </div>
        <div class="faq-item">
            <div class="faq-q" onclick="toggleFaq(this)">¿Los productos son compatibles con inducción?<i class="ti ti-plus"></i></div>
            <div class="faq-a">Sí. Todos los productos Velonox son compatibles con inducción, vitrocerámica, gas y horno convencional. El fondo difusor de triple capa garantiza rendimiento óptimo en cualquier fuente de calor.</div>
        </div>
        <div class="faq-item">
            <div class="faq-q" onclick="toggleFaq(this)">¿Qué cubre la garantía de 1 año?<i class="ti ti-plus"></i></div>
            <div class="faq-a">Nuestra garantía cubre cualquier defecto de fabricación: deformaciones, problemas con el fondo, soldaduras o acabados defectuosos. No cubre daños por mal uso, caídas o rayones por utensilios inadecuados.</div>
        </div>
        <div class="faq-item">
            <div class="faq-q" onclick="toggleFaq(this)">¿Puedo devolver un producto si no me convence?<i class="ti ti-plus"></i></div>
            <div class="faq-a">Sí. Tienes 30 días desde la recepción para solicitar una devolución. El producto debe estar en condiciones originales. Escríbenos por WhatsApp o formulario y gestionamos todo.</div>
        </div>
        <div class="faq-item">
            <div class="faq-q" onclick="toggleFaq(this)">¿Hacen envíos a toda Latinoamérica?<i class="ti ti-plus"></i></div>
            <div class="faq-a">Actualmente enviamos a Colombia, México, Perú y Chile. Si tu país no aparece en el checkout, escríbenos y buscamos una solución.</div>
        </div>
    </div>
</section>"""
            }
        },
        {
            "block_type": "footer",
            "config": {
                "store_name": "Velonox",
                "tagline": "Cocina de por vida.",
                "email": "contacto@velonox.co"
            }
        }
    ],
    "nosotros": [
        {
            "block_type": "content_hero",
            "config": {
                "eyebrow": "Colombia · 2026",
                "title_html": "Una sola misión.<br><em>Cocinas más sanas.</em>",
                "text": "Velonox nació de una convicción simple: los hogares latinoamericanos merecen cocinar sin venenos, sin excusas y sin pagar precios de lujo para lograrlo."
            }
        },
        {
            "block_type": "custom_html",
            "config": {
                "css": "",
                "html": """<section class="historia">
    <div>
        <p class="historia-eyebrow">Nuestra historia</p>
        <h2>Una decisión en la cocina que se convirtió en marca.</h2>
        <p>Todo comenzó con una pregunta incómoda: ¿qué está liberando realmente esa sartén antiadherente cuando se calienta? La respuesta fue el inicio de Velonox.</p>
        <p>En 2026, desde Colombia, emprendimos con una propuesta clara — ofrecer cocina en acero inoxidable grado 304 de calidad profesional, a un precio al que cualquier hogar latinoamericano pueda acceder.</p>
        <p>No somos una corporación. Somos un emprendimiento con convicción: la de que cambiar los materiales con los que cocinas puede cambiar la salud de tu familia para siempre.</p>
    </div>
    <div class="historia-img">
        <div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:1rem">
            <span class="historia-year">2026</span>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 56 56" width="80" height="80" style="opacity:.3">
                <polygon points="28,4 52,52 36,52 28,28 20,52 4,52" fill="#C8D8C0"/>
                <polygon points="28,28 52,52 36,52" fill="#1D7A4F"/>
                <rect x="4" y="32" width="48" height="3" fill="#1D7A4F"/>
            </svg>
        </div>
        <div class="historia-badge">
            <p><strong>Fundada en Colombia</strong> · Con visión para toda Latinoamérica</p>
        </div>
    </div>
</section>

<section class="proposito">
    <div class="proposito-inner">
        <p class="proposito-eyebrow">Nuestro propósito</p>
        <h2>Eliminar el teflón tóxico<br>de los hogares <em>latinoamericanos.</em></h2>
        <p>El teflón libera compuestos PFAS a temperaturas de cocción normales. Estos químicos se acumulan en el cuerpo y están vinculados a problemas hormonales, renales y de fertilidad. Lo peor: la mayoría de las familias latinas los usa a diario sin saberlo.</p>
        <p>Velonox existe para cambiar eso. No con miedo, sino con una alternativa real: acero inoxidable 304, el mismo estándar que usan los chefs profesionales, ahora accesible para tu hogar.</p>
        <div class="proposito-stats">
            <div class="proposito-stat"><span class="num">304</span><span class="label">Grado de acero<br>alimentario</span></div>
            <div class="proposito-stat"><span class="num">0</span><span class="label">Tóxicos liberados<br>al cocinar</span></div>
            <div class="proposito-stat"><span class="num">25+</span><span class="label">Años de vida útil<br>promedio</span></div>
            <div class="proposito-stat"><span class="num">∞</span><span class="label">Razones para<br>cambiar hoy</span></div>
        </div>
    </div>
</section>

<section class="mv">
    <div class="mv-grid">
        <div class="mv-card mv-mision">
            <i class="ti ti-target mv-icon"></i>
            <span class="mv-tag">Misión</span>
            <h3>Cocinas más sanas. Hoy, en tu hogar.</h3>
            <p>Ofrecer equipos de cocina en acero inoxidable grado 304 de calidad profesional, a precios honestos y accesibles para el hogar latinoamericano. Cada producto que fabricamos reemplaza un material tóxico por uno que dura décadas y no le cobra nada a la salud de tu familia.</p>
        </div>
        <div class="mv-card mv-vision">
            <i class="ti ti-telescope mv-icon"></i>
            <span class="mv-tag">Visión</span>
            <h3>Ser la marca de cocina de referencia en Latinoamérica.</h3>
            <p>Para 2030, queremos que Velonox sea sinónimo de cocina consciente en Colombia, México, Perú, Chile y más allá. Una marca en la que millones de familias latinoamericanas confíen no solo por la calidad de sus productos, sino por lo que representamos: salud, honestidad y durabilidad real.</p>
        </div>
    </div>
</section>

<section class="valores">
    <div class="valores-inner">
        <p class="valores-eyebrow">Lo que nos define</p>
        <h2>Nuestros valores</h2>
        <div class="valores-grid">
            <div class="valor-card"><div class="valor-num">01</div><p class="valor-title">Honestidad radical</p><p class="valor-text">Decimos lo que contienen nuestros productos, cómo se fabrican y por qué son mejores. Sin marketing vacío, sin superlativos sin sustancia. Calidad que se demuestra, no que se proclama.</p></div>
            <div class="valor-card"><div class="valor-num">02</div><p class="valor-title">Accesibilidad real</p><p class="valor-text">Premium no significa inalcanzable. Creemos que la calidad profesional debe estar al alcance de cualquier hogar latinoamericano, no solo de quienes pueden pagar marcas europeas.</p></div>
            <div class="valor-card"><div class="valor-num">03</div><p class="valor-title">Durabilidad como principio</p><p class="valor-text">Fabricamos para que dure 25 años, no para que se vuelva a comprar en 2. La sostenibilidad real no es un sello verde, es un producto que no termina en la basura cada temporada.</p></div>
            <div class="valor-card"><div class="valor-num">04</div><p class="valor-title">Salud sin negociación</p><p class="valor-text">Ningún producto Velonox contiene materiales que puedan comprometer la salud de quien cocina o de quien come. Este principio no es negociable, sin importar el costo de producción.</p></div>
        </div>
    </div>
</section>

<section class="cliente">
    <div class="cliente-inner">
        <div>
            <p class="cliente-eyebrow">Para quién existimos</p>
            <h2>Le hablamos a quien cocina con conciencia.</h2>
            <p>Nuestro cliente no busca lo más barato ni lo más costoso. Busca la mejor decisión. Es alguien que lee etiquetas, que se pregunta qué le está dando de comer a su familia y que está dispuesto a invertir una vez en algo que dure.</p>
            <p>Le hablamos a la persona que ya sabe que el teflón no es la respuesta, o que está a punto de descubrirlo. A quien le importa la salud de su hogar tanto como el precio que paga.</p>
            <div class="cliente-tags">
                <span class="cliente-tag">Consciente de la salud</span>
                <span class="cliente-tag">Latinoamérica</span>
                <span class="cliente-tag">Invierte en calidad</span>
                <span class="cliente-tag">Anti-teflón</span>
                <span class="cliente-tag">Hogar primero</span>
            </div>
        </div>
        <div class="cliente-visual">
            <div class="cliente-card"><i class="ti ti-heart"></i><strong>Salud familiar</strong><span>Cocinar sin químicos tóxicos todos los días</span></div>
            <div class="cliente-card"><i class="ti ti-coin"></i><strong>Precio honesto</strong><span>Calidad real sin pagar precio de lujo</span></div>
            <div class="cliente-card"><i class="ti ti-clock"></i><strong>Largo plazo</strong><span>Una compra que dura décadas</span></div>
            <div class="cliente-card"><i class="ti ti-map-pin"></i><strong>Latinoamérica</strong><span>Hecho para nuestra forma de cocinar</span></div>
        </div>
    </div>
</section>

<section class="compromiso">
    <p class="compromiso-eyebrow">Nuestro compromiso</p>
    <h2>Lo que prometemos, siempre.</h2>
    <p>Cada vez que compras Velonox, no solo estás comprando una olla o una sartén. Estás eligiendo una postura sobre cómo quieres vivir y alimentar a los tuyos.</p>
    <div class="compromiso-grid">
        <div class="compromiso-item"><i class="ti ti-certificate"></i><strong>Acero 304 certificado</strong><span>Grado alimentario verificado en cada producto</span></div>
        <div class="compromiso-item"><i class="ti ti-shield-check"></i><strong>Garantía 1 año</strong><span>Cubrimos defectos de fabricación sin preguntas</span></div>
        <div class="compromiso-item"><i class="ti ti-truck"></i><strong>Envío a toda LATAM</strong><span>Colombia, México, Perú, Chile y más</span></div>
        <div class="compromiso-item"><i class="ti ti-refresh"></i><strong>30 días de devolución</strong><span>Si no estás satisfecho, te devolvemos tu dinero</span></div>
        <div class="compromiso-item"><i class="ti ti-headset"></i><strong>Soporte real</strong><span>Personas reales respondiendo tus preguntas</span></div>
    </div>
</section>

<section class="cta">
    <p class="cta-eyebrow">Únete al cambio</p>
    <h2>Cocina de <em>por vida.</em></h2>
    <p>Empieza hoy. Un producto que reemplaza el teflón para siempre, que tu familia agradecerá durante décadas.</p>
    <a href="index.html" class="btn-primary">Ver la colección</a>
</section>"""
            }
        },
        {
            "block_type": "footer",
            "config": {
                "store_name": "Velonox",
                "tagline": "Cocina de por vida.",
                "email": "contacto@velonox.co"
            }
        }
    ],
    "politicas": [
        {
            "block_type": "content_hero",
            "config": {
                "eyebrow": "Transparencia total",
                "title_html": "Políticas de Velonox",
                "text": "Aquí explicamos claramente cómo funcionan nuestros envíos, devoluciones, garantías y el manejo de tu información personal."
            }
        },
        {
            "block_type": "custom_html",
            "config": {
                "css": "",
                "html": """<div class="policy-nav">
    <div class="policy-nav-inner">
        <a href="#envios" class="active" onclick="setActive(this)">📦 Envíos</a>
        <a href="#devoluciones" onclick="setActive(this)">↩️ Devoluciones</a>
        <a href="#garantia" onclick="setActive(this)">🛡️ Garantía</a>
        <a href="#privacidad" onclick="setActive(this)">🔒 Privacidad</a>
        <a href="#pagos" onclick="setActive(this)">💳 Pagos</a>
    </div>
</div>

<div class="content">

    <div class="policy-section" id="envios">
        <div class="section-header">
            <div class="section-icon"><i class="ti ti-truck"></i></div>
            <div><p class="section-eyebrow">Política de envíos</p><h2 class="section-title">Envíos y tiempos de entrega</h2></div>
        </div>
        <div class="policy-text">
            <div class="highlight"><i class="ti ti-info-circle"></i><p><strong>Envío gratis</strong> en pedidos mayores a $30 USD dentro de Colombia, y mayores a $40 USD para el resto de países. Para pedidos menores, el costo de envío se calcula al momento del checkout según tu ubicación.</p></div>
            <div class="info-cards">
                <div class="info-card"><i class="ti ti-map-pin"></i><strong>Colombia</strong><span>2 a 5 días hábiles</span></div>
                <div class="info-card"><i class="ti ti-world"></i><strong>México · Perú · Chile</strong><span>7 a 15 días hábiles</span></div>
                <div class="info-card"><i class="ti ti-package"></i><strong>Despacho</strong><span>1 a 2 días hábiles tras confirmar pago</span></div>
            </div>
            <h4>¿Cómo funciona el proceso?</h4>
            <ul>
                <li>Una vez confirmado tu pago, procesamos y empacamos tu pedido en 1 a 2 días hábiles.</li>
                <li>Recibirás un email con el número de guía de seguimiento cuando tu paquete sea despachado.</li>
                <li>Puedes rastrear tu pedido en tiempo real con ese número en la página del transportista.</li>
                <li>Si en 5 días hábiles no recibes tu guía de seguimiento, escríbenos por WhatsApp.</li>
            </ul>
            <h4>Países con cobertura actual</h4>
            <table class="policy-table">
                <thead><tr><th>País</th><th>Tiempo estimado</th><th>Envío gratis desde</th></tr></thead>
                <tbody>
                    <tr><td>🇨🇴 Colombia</td><td>2 a 5 días hábiles</td><td>$30 USD</td></tr>
                    <tr><td>🇲🇽 México</td><td>7 a 12 días hábiles</td><td>$40 USD</td></tr>
                    <tr><td>🇵🇪 Perú</td><td>8 a 15 días hábiles</td><td>$40 USD</td></tr>
                    <tr><td>🇨🇱 Chile</td><td>7 a 12 días hábiles</td><td>$40 USD</td></tr>
                </tbody>
            </table>
            <div class="warning"><i class="ti ti-alert-triangle"></i><p>Los tiempos de entrega son estimados y pueden variar por factores externos como aduanas, condiciones climáticas o temporadas de alta demanda. Si tu país no aparece en la lista, escríbenos — buscamos una solución.</p></div>
        </div>
    </div>

    <div class="policy-section" id="devoluciones">
        <div class="section-header">
            <div class="section-icon"><i class="ti ti-refresh"></i></div>
            <div><p class="section-eyebrow">Política de devoluciones</p><h2 class="section-title">Devoluciones y reembolsos</h2></div>
        </div>
        <div class="policy-text">
            <div class="highlight"><i class="ti ti-heart"></i><p><strong>30 días para decidir.</strong> Si por cualquier razón no estás satisfecho con tu compra, tienes 30 días calendario desde la fecha de recepción para solicitar una devolución.</p></div>
            <h4>Condiciones para devolución</h4>
            <ul>
                <li>El producto debe estar en condiciones originales — sin uso, sin daños y en su empaque original.</li>
                <li>Debes incluir la factura o comprobante de compra.</li>
                <li>La solicitud debe realizarse dentro de los 30 días calendario posteriores a la recepción.</li>
                <li>Los productos personalizados o de sets abiertos no son elegibles para devolución.</li>
            </ul>
            <h4>¿Cómo solicitar una devolución?</h4>
            <ul>
                <li><strong>Paso 1:</strong> Escríbenos por WhatsApp (+57 310 888 7296) o formulario de contacto indicando tu número de pedido y el motivo de la devolución.</li>
                <li><strong>Paso 2:</strong> Te enviaremos las instrucciones de empaque y la dirección de envío de devolución.</li>
                <li><strong>Paso 3:</strong> Una vez recibido e inspeccionado el producto (2 a 3 días hábiles), procesamos el reembolso.</li>
                <li><strong>Paso 4:</strong> El reembolso se acredita al método de pago original en 5 a 10 días hábiles.</li>
            </ul>
            <h4>¿Qué no es elegible para devolución?</h4>
            <ul>
                <li>Productos con daños causados por mal uso, caídas o uso inadecuado de utensilios.</li>
                <li>Productos sin empaque original.</li>
                <li>Solicitudes realizadas después de 30 días de la recepción.</li>
                <li>Productos de la categoría "Liquidación" o "Oferta final".</li>
            </ul>
        </div>
    </div>

    <div class="policy-section" id="garantia">
        <div class="section-header">
            <div class="section-icon"><i class="ti ti-shield-check"></i></div>
            <div><p class="section-eyebrow">Política de garantía</p><h2 class="section-title">Garantía de 1 año</h2></div>
        </div>
        <div class="policy-text">
            <div class="highlight"><i class="ti ti-certificate"></i><p>Todos los productos Velonox cuentan con <strong>garantía de 1 año contra defectos de fabricación</strong> desde la fecha de compra. Si algo falla por nuestra parte, lo resolvemos sin costo.</p></div>
            <h4>¿Qué cubre la garantía?</h4>
            <ul>
                <li>Deformaciones o alabeos del fondo difusor sin causa de mal uso.</li>
                <li>Defectos en soldaduras de mangos o tapas.</li>
                <li>Desprendimiento del acabado interior o exterior por defecto de fábrica.</li>
                <li>Fallas en la compatibilidad con inducción por defecto de fabricación.</li>
                <li>Cualquier defecto que impida el uso normal del producto.</li>
            </ul>
            <h4>¿Qué NO cubre la garantía?</h4>
            <ul>
                <li>Daños por caídas, golpes o impactos.</li>
                <li>Rayones causados por utensilios metálicos, estropajos abrasivos o lavavajillas en ciclos agresivos.</li>
                <li>Decoloración por exposición prolongada a fuego directo a máxima potencia.</li>
                <li>Daños por uso en condiciones no recomendadas (microondas, fogones a leña).</li>
                <li>Desgaste normal por uso prolongado.</li>
            </ul>
            <h4>¿Cómo hacer válida la garantía?</h4>
            <ul>
                <li>Contáctanos por WhatsApp con fotos del defecto y tu número de pedido.</li>
                <li>Evaluamos el caso en 24 a 48 horas hábiles.</li>
                <li>Si aplica, te enviamos un producto de reemplazo o gestionamos el reembolso sin costo adicional.</li>
            </ul>
        </div>
    </div>

    <div class="policy-section" id="privacidad">
        <div class="section-header">
            <div class="section-icon"><i class="ti ti-lock"></i></div>
            <div><p class="section-eyebrow">Política de privacidad</p><h2 class="section-title">Tus datos, tu privacidad</h2></div>
        </div>
        <div class="policy-text">
            <p>En Velonox tomamos la privacidad de tus datos muy en serio. Esta política explica qué información recopilamos, cómo la usamos y cómo la protegemos.</p>
            <h4>¿Qué información recopilamos?</h4>
            <ul>
                <li><strong>Datos de cuenta:</strong> nombre, email y contraseña (almacenada de forma encriptada, nunca en texto plano).</li>
                <li><strong>Datos de compra:</strong> dirección de envío, historial de pedidos y preferencias de producto.</li>
                <li><strong>Datos de pago:</strong> procesados exclusivamente por Bold. Velonox nunca almacena datos de tarjetas.</li>
                <li><strong>Datos de navegación:</strong> páginas visitadas y productos vistos, para mejorar tu experiencia.</li>
            </ul>
            <h4>¿Para qué usamos tu información?</h4>
            <ul>
                <li>Procesar y enviar tus pedidos.</li>
                <li>Enviarte actualizaciones sobre tu pedido por email.</li>
                <li>Mejorar nuestros productos y la experiencia en la tienda.</li>
                <li>Enviarte comunicaciones de marketing solo si das tu consentimiento explícito.</li>
            </ul>
            <h4>¿Compartimos tu información?</h4>
            <ul>
                <li>Con transportistas, exclusivamente los datos necesarios para la entrega.</li>
                <li>Con Bold para procesar pagos de forma segura.</li>
                <li>Nunca vendemos ni compartimos tu información con terceros para fines publicitarios.</li>
            </ul>
            <div class="highlight"><i class="ti ti-user-check"></i><p>Tienes derecho a solicitar la eliminación de tu cuenta y datos en cualquier momento. Escríbenos por WhatsApp o formulario de contacto y lo procesamos en menos de 72 horas.</p></div>
        </div>
    </div>

    <div class="policy-section" id="pagos">
        <div class="section-header">
            <div class="section-icon"><i class="ti ti-credit-card"></i></div>
            <div><p class="section-eyebrow">Política de pagos</p><h2 class="section-title">Medios de pago y seguridad</h2></div>
        </div>
        <div class="policy-text">
            <div class="highlight"><i class="ti ti-shield"></i><p>Todos los pagos en Velonox son procesados por <strong>Bold</strong>, pasarela de pagos colombiana. Tu información financiera nunca pasa por nuestros servidores.</p></div>
            <h4>Métodos de pago aceptados</h4>
            <ul>
                <li>Tarjetas de crédito y débito Visa, Mastercard y American Express.</li>
                <li>PSE y otros métodos de pago locales en Colombia.</li>
                <li>Pago contraentrega disponible para pedidos dentro de Colombia.</li>
            </ul>
            <h4>Seguridad de tus pagos</h4>
            <ul>
                <li>Conexión cifrada SSL en todas las páginas de checkout.</li>
                <li>Verificación de integridad de cada transacción antes de confirmar el pago.</li>
                <li>Velonox nunca almacena datos de tarjetas de crédito o débito.</li>
            </ul>
            <h4>¿Qué pasa si mi pago falla?</h4>
            <ul>
                <li>No se realiza ningún cargo si el pago no se completa exitosamente.</li>
                <li>Puedes intentarlo de nuevo con la misma u otra tarjeta.</li>
                <li>Si el problema persiste, escríbenos por WhatsApp y te ayudamos a resolverlo.</li>
            </ul>
            <h4>Moneda y precios</h4>
            <p>Todos los precios en Velonox están expresados en <strong>dólares estadounidenses (USD)</strong>. Como Bold procesa los pagos en pesos colombianos (COP), el monto se convierte automáticamente a la tasa de cambio vigente al momento de tu compra.</p>
        </div>
    </div>

    <div class="cta-box">
        <strong>¿Tienes alguna duda sobre nuestras políticas?</strong>
        <p>Estamos disponibles de lunes a viernes de 8am a 6pm y sábados de 9am a 1pm. Respondemos en menos de 2 horas.</p>
        <a href="https://wa.me/573108887296?text=Hola%20Velonox%2C%20tengo%20una%20duda%20sobre%20sus%20pol%C3%ADticas" target="_blank" class="whatsapp-btn">
            <i class="ti ti-brand-whatsapp"></i> Hablar con nosotros
        </a>
    </div>

</div>"""
            }
        },
        {
            "block_type": "footer",
            "config": {
                "store_name": "Velonox",
                "tagline": "Cocina de por vida.",
                "email": "contacto@velonox.co"
            }
        }
    ],
    "terminos": [
        {
            "block_type": "content_hero",
            "config": {
                "eyebrow": "Legal",
                "title_html": "Términos y Condiciones",
                "text": "Al comprar en Velonox aceptas estos términos. Los redactamos en lenguaje claro para que entiendas exactamente tus derechos y los nuestros.<br><span style=\"font-size:12px;color:#4A6A5A\">Última actualización: julio de 2026</span>"
            }
        },
        {
            "block_type": "custom_html",
            "config": {
                "css": "",
                "html": """<div class="content">

    <div class="index-box">
        <h3>Contenido</h3>
        <div class="index-list">
            <a href="#aceptacion">1. Aceptación de términos</a>
            <a href="#productos">2. Productos y precios</a>
            <a href="#cuenta">3. Cuenta de usuario</a>
            <a href="#pedidos">4. Pedidos y pagos</a>
            <a href="#envios">5. Envíos</a>
            <a href="#devoluciones">6. Devoluciones</a>
            <a href="#garantia">7. Garantía</a>
            <a href="#propiedad">8. Propiedad intelectual</a>
            <a href="#responsabilidad">9. Limitación de responsabilidad</a>
            <a href="#modificaciones">10. Modificaciones</a>
        </div>
    </div>

    <div class="tc-section" id="aceptacion">
        <div class="tc-num">01</div>
        <h2 class="tc-title">Aceptación de términos</h2>
        <div class="tc-text">
            <p>Al acceder y utilizar el sitio web de Velonox (velonox.co) y realizar una compra, aceptas estar sujeto a estos Términos y Condiciones. Si no estás de acuerdo con alguno de estos términos, te pedimos que no utilices nuestros servicios.</p>
            <p>Estos términos aplican a todos los visitantes, usuarios y personas que accedan o usen el servicio. Velonox se reserva el derecho de actualizar estos términos en cualquier momento, notificando los cambios en esta misma página.</p>
            <div class="highlight"><i class="ti ti-info-circle"></i><p>Al finalizar una compra, confirmas que eres mayor de 18 años o que cuentas con autorización de un adulto responsable, y que los datos que proporcionas son verídicos y completos.</p></div>
        </div>
    </div>

    <div class="tc-section" id="productos">
        <div class="tc-num">02</div>
        <h2 class="tc-title">Productos y precios</h2>
        <div class="tc-text">
            <p>Velonox se esfuerza por mostrar los colores, dimensiones y características de los productos con la mayor precisión posible. Sin embargo, no garantizamos que la visualización en tu pantalla sea 100% fiel al producto físico.</p>
            <h4>Sobre los precios</h4>
            <ul>
                <li>Todos los precios están expresados en dólares estadounidenses (USD) e incluyen el producto pero no el costo de envío, salvo que se indique expresamente.</li>
                <li>Velonox se reserva el derecho de modificar precios en cualquier momento sin previo aviso.</li>
                <li>Una vez confirmado y pagado tu pedido, el precio no cambia aunque se modifique posteriormente en la tienda.</li>
                <li>En caso de error de precio evidente en la tienda, nos reservamos el derecho de cancelar el pedido y reembolsar el monto pagado.</li>
            </ul>
            <h4>Disponibilidad</h4>
            <p>El stock mostrado en la tienda es en tiempo real. Velonox no garantiza la disponibilidad permanente de ningún producto. Si un producto se agota después de realizar tu pago, te notificaremos y ofreceremos un reembolso completo o producto alternativo.</p>
        </div>
    </div>

    <div class="tc-section" id="cuenta">
        <div class="tc-num">03</div>
        <h2 class="tc-title">Cuenta de usuario</h2>
        <div class="tc-text">
            <p>Para realizar compras en Velonox debes crear una cuenta. Eres responsable de mantener la confidencialidad de tu contraseña y de todas las actividades que ocurran bajo tu cuenta.</p>
            <ul>
                <li>Debes proporcionar información precisa, completa y actualizada al registrarte.</li>
                <li>Eres responsable de notificarnos inmediatamente ante cualquier uso no autorizado de tu cuenta.</li>
                <li>Velonox no será responsable por pérdidas causadas por el uso no autorizado de tu cuenta.</li>
                <li>Nos reservamos el derecho de cerrar cuentas que violen estos términos.</li>
            </ul>
            <p>Puedes solicitar la eliminación de tu cuenta y datos en cualquier momento contactándonos por WhatsApp. Procesamos la solicitud en menos de 72 horas.</p>
        </div>
    </div>

    <div class="tc-section" id="pedidos">
        <div class="tc-num">04</div>
        <h2 class="tc-title">Pedidos y pagos</h2>
        <div class="tc-text">
            <p>Al realizar un pedido, recibirás un email de confirmación. Este email no constituye la aceptación definitiva del pedido — la venta se confirma cuando el pago es procesado exitosamente.</p>
            <h4>Procesamiento de pagos</h4>
            <ul>
                <li>Los pagos son procesados por Bold, pasarela de pagos colombiana.</li>
                <li>Velonox nunca almacena datos de tarjetas de crédito o débito.</li>
                <li>Aceptamos tarjetas Visa, Mastercard, American Express, PSE y pago contraentrega en Colombia.</li>
                <li>El cargo se realiza en el momento de confirmar el pedido.</li>
            </ul>
            <h4>Cancelación de pedidos</h4>
            <p>Puedes cancelar tu pedido sin costo dentro de las primeras 2 horas de realizado, siempre que no haya sido despachado. Para cancelaciones, contáctanos inmediatamente por WhatsApp.</p>
            <div class="warning"><i class="ti ti-alert-triangle"></i><p>Una vez despachado el pedido, no es posible cancelarlo. En ese caso aplica nuestra política de devoluciones de 30 días una vez recibido el producto.</p></div>
        </div>
    </div>

    <div class="tc-section" id="envios">
        <div class="tc-num">05</div>
        <h2 class="tc-title">Envíos</h2>
        <div class="tc-text">
            <p>Los tiempos de entrega son estimados y pueden variar por factores externos como aduanas, condiciones climáticas o temporadas de alta demanda. Velonox no se responsabiliza por demoras causadas por terceros.</p>
            <ul>
                <li>Colombia: 2 a 5 días hábiles desde el despacho.</li>
                <li>México, Perú, Chile: 7 a 15 días hábiles desde el despacho.</li>
                <li>El envío es gratuito en pedidos mayores a $30 USD.</li>
                <li>Recibirás un número de guía de seguimiento por email una vez despachado tu pedido.</li>
            </ul>
            <p>Velonox no se hace responsable por paquetes extraviados una vez entregados a la empresa transportista, aunque haremos todo lo posible por ayudarte a rastrear y recuperar tu envío.</p>
        </div>
    </div>

    <div class="tc-section" id="devoluciones">
        <div class="tc-num">06</div>
        <h2 class="tc-title">Devoluciones y reembolsos</h2>
        <div class="tc-text">
            <p>Tienes 30 días calendario desde la recepción del producto para solicitar una devolución, siempre que el producto esté en condiciones originales, sin uso y con su empaque original.</p>
            <ul>
                <li>Los reembolsos se procesan al método de pago original en 5 a 10 días hábiles.</li>
                <li>Los costos de envío de devolución son responsabilidad del cliente, salvo que el producto presente un defecto de fabricación.</li>
                <li>Productos de liquidación, ofertas finales o kits parcialmente abiertos no son elegibles para devolución.</li>
            </ul>
            <p>Para más detalles, consulta nuestra <a href="politicas.html#devoluciones" style="color:#1D7A4F">Política de Devoluciones</a> completa.</p>
        </div>
    </div>

    <div class="tc-section" id="garantia">
        <div class="tc-num">07</div>
        <h2 class="tc-title">Garantía</h2>
        <div class="tc-text">
            <p>Todos los productos Velonox cuentan con garantía de 1 año contra defectos de fabricación desde la fecha de compra. La garantía no cubre daños por mal uso, caídas o desgaste normal.</p>
            <p>Para hacer válida la garantía, contacta a nuestro equipo por WhatsApp con fotos del defecto y tu número de pedido. Evaluamos cada caso en 24 a 48 horas hábiles.</p>
            <p>Para más detalles, consulta nuestra <a href="politicas.html#garantia" style="color:#1D7A4F">Política de Garantía</a> completa.</p>
        </div>
    </div>

    <div class="tc-section" id="propiedad">
        <div class="tc-num">08</div>
        <h2 class="tc-title">Propiedad intelectual</h2>
        <div class="tc-text">
            <p>Todo el contenido de la tienda Velonox — incluyendo textos, imágenes, logotipos, diseños, videos y el software de la plataforma — es propiedad de Velonox o de sus licenciantes y está protegido por leyes de propiedad intelectual.</p>
            <ul>
                <li>No está permitido reproducir, distribuir, modificar o usar el contenido de Velonox con fines comerciales sin autorización escrita previa.</li>
                <li>El uso personal y no comercial del contenido está permitido, citando la fuente.</li>
                <li>Las marcas Velonox, el logotipo y el slogan "Cocina de por vida" son marca registrada.</li>
            </ul>
        </div>
    </div>

    <div class="tc-section" id="responsabilidad">
        <div class="tc-num">09</div>
        <h2 class="tc-title">Limitación de responsabilidad</h2>
        <div class="tc-text">
            <p>Velonox no será responsable por daños indirectos, incidentales, especiales o consecuentes derivados del uso o la imposibilidad de uso de nuestros productos o servicios.</p>
            <ul>
                <li>La responsabilidad máxima de Velonox ante cualquier reclamación se limita al valor del pedido en cuestión.</li>
                <li>Velonox no garantiza que el sitio web esté libre de errores, interrupciones o virus.</li>
                <li>No nos responsabilizamos por el contenido de sitios web de terceros a los que se pueda acceder desde nuestra tienda.</li>
            </ul>
            <div class="highlight"><i class="ti ti-shield-check"></i><p>Estas limitaciones aplican en la medida máxima permitida por la ley colombiana y las leyes aplicables en cada país de destino.</p></div>
        </div>
    </div>

    <div class="tc-section" id="modificaciones">
        <div class="tc-num">10</div>
        <h2 class="tc-title">Modificaciones y legislación aplicable</h2>
        <div class="tc-text">
            <p>Velonox se reserva el derecho de modificar estos Términos y Condiciones en cualquier momento. Los cambios entran en vigor en el momento de su publicación en esta página. El uso continuado de la tienda después de la publicación de cambios implica la aceptación de los nuevos términos.</p>
            <p>Estos términos se rigen por las leyes de la República de Colombia. Cualquier disputa será sometida a los tribunales competentes de Colombia, sin perjuicio de las leyes de protección al consumidor aplicables en el país de residencia del comprador.</p>
            <p>Para cualquier consulta sobre estos términos, contáctanos:</p>
            <ul>
                <li>WhatsApp: +57 310 888 7296</li>
                <li>Formulario: <a href="contacto.html" style="color:#1D7A4F">velonox.co/contacto</a></li>
            </ul>
        </div>
    </div>

    <div class="cta-box">
        <strong>¿Tienes dudas sobre estos términos?</strong>
        <p>Escríbenos y te explicamos cualquier punto con claridad. Respondemos en menos de 2 horas en horario hábil.</p>
        <a href="https://wa.me/573108887296?text=Hola%20Velonox%2C%20tengo%20una%20duda%20sobre%20los%20t%C3%A9rminos%20y%20condiciones" target="_blank" class="whatsapp-btn">
            <i class="ti ti-brand-whatsapp"></i> Hablar con nosotros
        </a>
    </div>

</div>"""
            }
        },
        {
            "block_type": "footer",
            "config": {
                "store_name": "Velonox",
                "tagline": "Cocina de por vida.",
                "email": "contacto@velonox.co"
            }
        }
    ],
    "categorias": [
        {
            "block_type": "content_hero",
            "config": {
                "eyebrow": "Acero inoxidable · Grado 304",
                "title_html": "Todo para tu <em>cocina.</em>",
                "text": "Explora nuestra colección organizada por categoría. Sin teflón, sin tóxicos, sin excusas."
            }
        },
        {
            "block_type": "custom_html",
            "config": {
                "css": "",
                "html": """<section class="cats-section">
    <p style="font-size:11px;font-weight:500;letter-spacing:.18em;color:#1D7A4F;text-transform:uppercase;margin-bottom:.4rem">Colección</p>
    <h2 style="font-family:'Playfair Display',serif;font-size:28px;font-weight:700;color:#0F1A14">¿Qué estás buscando?</h2>
    <div class="cats-grid" id="cats-grid">
        <div class="loading">Cargando categorías...</div>
    </div>
</section>
<div class="strip">
    <div class="strip-inner">
        <div class="strip-item"><i class="ti ti-certificate"></i><strong>Acero 304 certificado</strong><span>Grado alimentario en cada producto</span></div>
        <div class="strip-item"><i class="ti ti-truck"></i><strong>Envío gratis</strong><span>En compras desde $30 USD</span></div>
        <div class="strip-item"><i class="ti ti-shield-check"></i><strong>Garantía 1 año</strong><span>Contra defectos de fabricación</span></div>
        <div class="strip-item"><i class="ti ti-refresh"></i><strong>30 días devolución</strong><span>Sin preguntas, sin complicaciones</span></div>
    </div>
</div>
<section class="cta">
    <p class="cta-eyebrow">¿No sabes por dónde empezar?</p>
    <h2>Habla con nosotros</h2>
    <p>Te ayudamos a elegir el set ideal para tu cocina y tu presupuesto.</p>
    <a href="https://wa.me/573108887296?text=Hola%20Velonox%2C%20quiero%20asesor%C3%ADa%20para%20elegir%20mis%20productos" target="_blank" class="btn-primary">
        <i class="ti ti-brand-whatsapp"></i> Asesoría por WhatsApp
    </a>
</section>
<footer>
    <div class="footer-top">
        <div><div class="footer-logo"><span class="a">Velo</span><span class="b">nox</span></div><p class="footer-tagline">Cocina de por vida.</p></div>
        <div class="footer-col"><p>Tienda</p><a href="catalogo.html">Catálogo</a><a href="categorias.html">Categorías</a><a href="index.html">Inicio</a></div>
        <div class="footer-col"><p>Ayuda</p><a href="contacto.html">Contáctanos</a><a href="politicas.html">Envíos</a><a href="politicas.html#devoluciones">Devoluciones</a></div>
        <div class="footer-col"><p>Nosotros</p><a href="nosotros.html">Nuestra historia</a><a href="nosotros.html">Por qué acero</a></div>
        <div class="footer-col"><p>Legal</p><a href="terminos.html">Términos</a><a href="politicas.html#privacidad">Privacidad</a></div>
    </div>
    <div class="footer-bottom">
        <p class="footer-copy">© 2026 Velonox. Todos los derechos reservados.</p>
        <div class="footer-social"><a href="https://www.instagram.com/velonox__?igsh=MXhsOXhmcjA5MHI3NA%3D%3D&amp;utm_source=qr" target="_blank" rel="noopener"><i class="ti ti-brand-instagram"></i></a><a href="https://www.tiktok.com/@velonox5?_r=1&amp;_t=ZS-98EK8bwblET" target="_blank" rel="noopener"><i class="ti ti-brand-tiktok"></i></a><a href="https://www.facebook.com/share/1EHVcp5a2P/?mibextid=wwXIfr" target="_blank" rel="noopener"><i class="ti ti-brand-facebook"></i></a></div>
    </div>
</footer>"""
            }
        }
    ],
    "catalogo": [
        {
            "block_type": "custom_html",
            "config": {
                "css": "",
                "html": """<div class="breadcrumb">
    <a href="index.html">Inicio</a><span class="sep">›</span>
    <a href="categorias.html">Categorías</a><span class="sep">›</span>
    <span class="current" id="breadcrumb-cat">Cargando...</span>
</div>
<div class="cat-header">
    <div class="cat-header-inner">
        <div class="cat-header-icon"><i id="cat-icon" class="ti ti-tools-kitchen-2"></i></div>
        <div>
            <p class="cat-eyebrow">Colección Velonox</p>
            <h1 class="cat-title" id="cat-title">Cargando...</h1>
            <p class="cat-desc" id="cat-desc"></p>
        </div>
    </div>
</div>
<div class="toolbar">
    <div class="toolbar-left">
        <button class="filter-btn active" onclick="filterProducts('all',this)">Todos</button>
        <button class="filter-btn" onclick="filterProducts('in-stock',this)">En stock</button>
    </div>
    <div style="display:flex;align-items:center;gap:1rem">
        <span class="results-count" id="results-count"></span>
        <select class="sort-select" onchange="sortProducts(this.value)">
            <option value="default">Ordenar por</option>
            <option value="price-asc">Menor precio</option>
            <option value="price-desc">Mayor precio</option>
            <option value="name">Nombre A-Z</option>
        </select>
    </div>
</div>
<div class="products-section">
    <div class="prod-grid" id="prod-grid">
        <div class="empty"><i class="ti ti-loader"></i><p>Cargando productos...</p></div>
    </div>
</div>
<div class="other-cats" id="other-cats-section" style="display:none">
    <div class="other-cats-inner">
        <h3>Explorar otras categorías</h3>
        <div class="other-cats-grid" id="other-cats-grid"></div>
    </div>
</div>
<footer>
    <div class="footer-top">
        <div><div class="footer-logo"><span class="a">Velo</span><span class="b">nox</span></div><p class="footer-tagline">Cocina de por vida.</p></div>
        <div class="footer-col"><p>Tienda</p><a href="catalogo.html">Catálogo</a><a href="categorias.html">Categorías</a></div>
        <div class="footer-col"><p>Ayuda</p><a href="contacto.html">Contáctanos</a><a href="politicas.html">Envíos</a></div>
        <div class="footer-col"><p>Nosotros</p><a href="nosotros.html">Nuestra historia</a></div>
        <div class="footer-col"><p>Legal</p><a href="terminos.html">Términos</a><a href="politicas.html#privacidad">Privacidad</a></div>
    </div>
    <div class="footer-bottom">
        <p class="footer-copy">© 2026 Velonox. Todos los derechos reservados.</p>
        <div class="footer-social"><a href="https://www.instagram.com/velonox__?igsh=MXhsOXhmcjA5MHI3NA%3D%3D&amp;utm_source=qr" target="_blank" rel="noopener"><i class="ti ti-brand-instagram"></i></a><a href="https://www.tiktok.com/@velonox5?_r=1&amp;_t=ZS-98EK8bwblET" target="_blank" rel="noopener"><i class="ti ti-brand-tiktok"></i></a><a href="https://www.facebook.com/share/1EHVcp5a2P/?mibextid=wwXIfr" target="_blank" rel="noopener"><i class="ti ti-brand-facebook"></i></a></div>
    </div>
</footer>"""
            }
        }
    ],
    "tienda": [
        {
            "block_type": "custom_html",
            "config": {
                "css": "",
                "html": """<section class="hero">
    <div class="hero-inner">
        <div class="hero-text">
            <p class="eyebrow">Colección completa · Acero 304</p>
            <h1>Todo Velonox,<br>en un <em>solo lugar.</em></h1>
            <p class="sub">Explora, filtra y encuentra el producto perfecto para tu cocina. Sin teflón, sin tóxicos, sin excusas.</p>
        </div>
        <div class="hero-stats">
            <div class="hero-stat">
                <span class="num" id="stat-products">—</span>
                <span class="label">Productos<br>disponibles</span>
            </div>
            <div class="hero-stat">
                <span class="num">304</span>
                <span class="label">Grado de<br>acero</span>
            </div>
            <div class="hero-stat">
                <span class="num">2</span>
                <span class="label">Años de<br>garantía</span>
            </div>
        </div>
    </div>
</section>

<div class="toolbar">
    <div class="toolbar-inner">
        <div class="search-wrap">
            <i class="ti ti-search"></i>
            <input type="text" class="search-input" id="search-input"
                placeholder="Buscar productos..."
                oninput="handleSearch(this.value)">
        </div>
        <div class="filters" id="cat-filters">
            <button class="filter-btn active" onclick="filterByCat('',this)">Todos</button>
        </div>
        <div class="toolbar-right">
            <span class="results-count" id="results-count"></span>
            <select class="sort-select" onchange="handleSort(this.value)">
                <option value="default">Ordenar</option>
                <option value="price-asc">Menor precio</option>
                <option value="price-desc">Mayor precio</option>
                <option value="name">A — Z</option>
                <option value="stock">Con stock</option>
            </select>
        </div>
    </div>
</div>

<div class="main">
    <div class="prod-grid" id="prod-grid">
        <div>
            <div class="skeleton" style="height:200px;margin-bottom:.5rem"></div>
            <div class="skeleton" style="height:14px;width:80%;margin-bottom:.4rem"></div>
            <div class="skeleton" style="height:12px;width:50%"></div>
        </div>
        <div>
            <div class="skeleton" style="height:200px;margin-bottom:.5rem"></div>
            <div class="skeleton" style="height:14px;width:80%;margin-bottom:.4rem"></div>
            <div class="skeleton" style="height:12px;width:50%"></div>
        </div>
        <div>
            <div class="skeleton" style="height:200px;margin-bottom:.5rem"></div>
            <div class="skeleton" style="height:14px;width:80%;margin-bottom:.4rem"></div>
            <div class="skeleton" style="height:12px;width:50%"></div>
        </div>
        <div>
            <div class="skeleton" style="height:200px;margin-bottom:.5rem"></div>
            <div class="skeleton" style="height:14px;width:80%;margin-bottom:.4rem"></div>
            <div class="skeleton" style="height:12px;width:50%"></div>
        </div>
        <div>
            <div class="skeleton" style="height:200px;margin-bottom:.5rem"></div>
            <div class="skeleton" style="height:14px;width:80%;margin-bottom:.4rem"></div>
            <div class="skeleton" style="height:12px;width:50%"></div>
        </div>
        <div>
            <div class="skeleton" style="height:200px;margin-bottom:.5rem"></div>
            <div class="skeleton" style="height:14px;width:80%;margin-bottom:.4rem"></div>
            <div class="skeleton" style="height:12px;width:50%"></div>
        </div>
    </div>
</div>

<div class="cta-bottom">
    <p class="eyebrow">¿Necesitas ayuda?</p>
    <h2>Te ayudamos a<br>elegir lo <em>ideal.</em></h2>
    <p class="sub">Cuéntanos cómo cocinas y te recomendamos el set perfecto para tu hogar.</p>
    <a href="https://wa.me/573108887296?text=Hola%20Velonox%2C%20necesito%20ayuda%20para%20elegir%20productos" target="_blank" class="btn-wa">
        <i class="ti ti-brand-whatsapp"></i>
        Asesoría gratis por WhatsApp
    </a>
</div>

<footer>
    <div class="footer-top">
        <div>
            <div class="footer-logo"><span class="a">Velo</span><span class="b">nox</span></div>
            <p class="footer-tagline">Cocina de por vida.</p>
        </div>
        <div class="footer-col"><p>Tienda</p>
            <a href="catalogo.html">Todos los productos</a>
            <a href="categorias.html">Categorías</a>
            <a href="index.html">Inicio</a>
        </div>
        <div class="footer-col"><p>Ayuda</p>
            <a href="contacto.html">Contáctanos</a>
            <a href="politicas.html">Envíos</a>
            <a href="politicas.html#devoluciones">Devoluciones</a>
            <a href="politicas.html#garantia">Garantía</a>
        </div>
        <div class="footer-col"><p>Nosotros</p>
            <a href="nosotros.html">Nuestra historia</a>
            <a href="nosotros.html">Por qué acero</a>
        </div>
        <div class="footer-col"><p>Legal</p>
            <a href="terminos.html">Términos</a>
            <a href="politicas.html#privacidad">Privacidad</a>
        </div>
    </div>
    <div class="footer-bottom">
        <p class="footer-copy">© 2026 Velonox. Todos los derechos reservados.</p>
        <div class="footer-social">
            <a href="https://www.instagram.com/velonox__?igsh=MXhsOXhmcjA5MHI3NA%3D%3D&amp;utm_source=qr" target="_blank" rel="noopener"><i class="ti ti-brand-instagram"></i></a>
            <a href="https://www.tiktok.com/@velonox5?_r=1&amp;_t=ZS-98EK8bwblET" target="_blank" rel="noopener"><i class="ti ti-brand-tiktok"></i></a>
            <a href="https://www.facebook.com/share/1EHVcp5a2P/?mibextid=wwXIfr" target="_blank" rel="noopener"><i class="ti ti-brand-facebook"></i></a>
        </div>
    </div>
</footer>"""
            }
        }
    ],
}


@router.get("/", response_model=List[BlockResponse])
def get_layout(page: str = "home", db: Session = Depends(get_db)):
    """
    Devuelve todos los bloques del layout de una página, ordenados.
    Si no hay bloques en la DB para esa página devuelve los bloques por defecto.
    Público — lo llama la tienda al cargar.
    """
    blocks = (
        db.query(StoreLayout)
        .filter(StoreLayout.page_slug == page)
        .order_by(StoreLayout.order_index)
        .all()
    )

    if not blocks:
        # Primera vez para esta página — inicializa con los bloques por defecto
        if page == "home":
            seed = DEFAULT_BLOCKS
        elif page in CONTENT_PAGE_BLOCKS:
            seed = [
                {
                    "id": f"block-{page}-{i}",
                    "block_type": b["block_type"],
                    "order_index": i,
                    "is_visible": True,
                    "config": b["config"],
                }
                for i, b in enumerate(CONTENT_PAGE_BLOCKS[page])
            ]
        else:
            seed = []

        for block_data in seed:
            block = StoreLayout(
                id=block_data["id"],
                page_slug=page,
                block_type=block_data["block_type"],
                order_index=block_data["order_index"],
                is_visible=block_data["is_visible"],
                config=json.dumps(block_data["config"])
            )
            db.add(block)
        if seed:
            db.commit()
            blocks = (
                db.query(StoreLayout)
                .filter(StoreLayout.page_slug == page)
                .order_by(StoreLayout.order_index)
                .all()
            )

    # Parsear el config JSON antes de devolver
    result = []
    for block in blocks:
        result.append(BlockResponse(
            id=block.id,
            block_type=block.block_type,
            order_index=block.order_index,
            is_visible=block.is_visible,
            config=json.loads(block.config)
        ))

    return result


@router.put("/")
def update_layout(
    data: LayoutUpdate,
    page: str = "home",
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin)
):
    """
    Guarda el layout completo de una página.
    Reemplaza todos los bloques existentes de esa página con los nuevos.
    Antes de sobreescribir, archiva el estado actual en el historial (ver /layout/history).
    Solo administradores.
    """
    _snapshot_current_layout(db, page)

    # Borra los bloques actuales de esta página únicamente
    db.query(StoreLayout).filter(StoreLayout.page_slug == page).delete()

    # Inserta los nuevos en el orden recibido
    for i, block in enumerate(data.blocks):
        new_block = StoreLayout(
            id=block.id if block.id else str(uuid.uuid4()),
            page_slug=page,
            block_type=block.block_type,
            order_index=i,
            is_visible=block.is_visible,
            config=json.dumps(block.config)
        )
        db.add(new_block)

    db.commit()
    return {"mensaje": "Layout guardado ✅"}


@router.get("/history")
def get_layout_history(
    page: str = "home",
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin)
):
    """Lista las versiones guardadas de una página, más reciente primero. Solo administradores."""
    rows = (
        db.query(StoreLayoutHistory)
        .filter(StoreLayoutHistory.page_slug == page)
        .order_by(StoreLayoutHistory.created_at.desc())
        .all()
    )
    result = []
    for row in rows:
        blocks = json.loads(row.blocks)
        result.append({
            "id": row.id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "block_count": len(blocks),
            "block_types": [b["block_type"] for b in blocks],
        })
    return result


@router.post("/restore/{history_id}")
def restore_layout(
    history_id: str,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin)
):
    """Restaura una versión anterior del layout de una página. Solo administradores."""
    version = db.query(StoreLayoutHistory).filter(StoreLayoutHistory.id == history_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Versión no encontrada")

    page = version.page_slug
    # Archiva el estado actual antes de restaurar, para poder deshacer la restauración también
    _snapshot_current_layout(db, page)

    db.query(StoreLayout).filter(StoreLayout.page_slug == page).delete()
    blocks = json.loads(version.blocks)
    for i, block in enumerate(blocks):
        db.add(StoreLayout(
            id=block.get("id") or str(uuid.uuid4()),
            page_slug=page,
            block_type=block["block_type"],
            order_index=i,
            is_visible=block.get("is_visible", True),
            config=json.dumps(block["config"]),
        ))

    db.commit()
    return {"mensaje": "Versión restaurada ✅"}


@router.post("/reset")
def reset_layout(
    page: str = "home",
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin)
):
    """
    Borra los bloques guardados de una página para que vuelva a los bloques
    por defecto de fábrica en la siguiente carga. El estado actual queda
    archivado en el historial por si se quiere deshacer. Solo administradores.
    """
    _snapshot_current_layout(db, page)
    db.query(StoreLayout).filter(StoreLayout.page_slug == page).delete()
    db.commit()
    return {"mensaje": "Página restablecida a los valores de fábrica ✅"}


@router.post("/blocks")
def add_block(
    block: BlockConfig,
    page: str = "home",
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin)
):
    """Agrega un nuevo bloque al layout de una página. Solo administradores."""
    # Obtener el índice más alto actual dentro de esa página
    last = (
        db.query(StoreLayout)
        .filter(StoreLayout.page_slug == page)
        .order_by(StoreLayout.order_index.desc())
        .first()
    )
    next_index = (last.order_index + 1) if last else 0

    new_block = StoreLayout(
        id=str(uuid.uuid4()),
        page_slug=page,
        block_type=block.block_type,
        order_index=next_index,
        is_visible=block.is_visible,
        config=json.dumps(block.config)
    )
    db.add(new_block)
    db.commit()
    db.refresh(new_block)

    return BlockResponse(
        id=new_block.id,
        block_type=new_block.block_type,
        order_index=new_block.order_index,
        is_visible=new_block.is_visible,
        config=json.loads(new_block.config)
    )


@router.delete("/blocks/{block_id}")
def delete_block(
    block_id: str,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin)
):
    """Elimina un bloque del layout. Solo administradores."""
    block = db.query(StoreLayout).filter(StoreLayout.id == block_id).first()
    if block:
        db.delete(block)
        db.commit()
    return {"mensaje": "Bloque eliminado ✅"}


@router.post("/ai-generate")
def ai_generate(
    data: AIGenerateRequest,
    admin=Depends(get_current_admin)
):
    """Genera HTML/CSS con IA para bloques personalizados. Solo administradores."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="Asistente IA no configurado (falta ANTHROPIC_API_KEY)")

    system_prompt = (
        "Eres un experto en HTML y CSS para e-commerce. "
        "Genera una sección HTML/CSS profesional para una tienda online. "
        "La sección debe: tener diseño moderno y limpio, usar colores que combinen con azul (#2563eb) como color primario, "
        "ser responsive, NO usar frameworks externos (solo HTML y CSS puro). "
        "Responde SOLO con un objeto JSON con esta estructura exacta, sin explicaciones ni markdown: "
        '{"html": "el HTML completo aquí", "css": "el CSS adicional aquí si lo separaste"}. '
        "El HTML puede incluir estilos inline o una etiqueta <style> interna."
    )

    try:
        resp = http_requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 1500,
                "system": system_prompt,
                "messages": [{"role": "user", "content": data.prompt}],
            },
            timeout=30,
        )
    except http_requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="El servicio de IA tardó demasiado, intenta de nuevo")
    except http_requests.exceptions.RequestException:
        raise HTTPException(status_code=502, detail="No se pudo contactar el servicio de IA")

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Error al generar contenido con IA")

    text = resp.json()["content"][0]["text"]
    try:
        clean = text.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(clean)
    except Exception:
        parsed = {"html": text, "css": ""}

    return {"html": parsed.get("html", ""), "css": parsed.get("css", "")}
