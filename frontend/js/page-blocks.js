// ─── Renderizador compartido de bloques para páginas de contenido ────────────
// Usado por contacto.html, nosotros.html, politicas.html y terminos.html.
// Requiere que js/api.js se haya cargado antes (usa API_URL).

async function initPageBlocks(slug) {
    const container = document.getElementById("layout-container");
    if (!container) return;

    // TRM y layout se piden en paralelo (antes en fila). Si hay una versión
    // guardada de la última visita se pinta al instante, y solo se vuelve a
    // pintar si la versión fresca del backend es distinta.
    const cacheKey = "page_" + slug;
    const cached = vxCacheGet(cacheKey);
    const trmBefore = VX_TRM;
    const trmP = loadTRM();
    const layoutP = fetch(`${API_URL}/layout/?page=${slug}`).then(r => {
        if (!r.ok) throw new Error(`layout ${r.status}`);
        return r.json();
    });

    if (cached) renderPageBlocksInto(container, cached);

    try {
        const [blocks] = await Promise.all([layoutP, trmP]);
        const changed = !cached
            || JSON.stringify(cached) !== JSON.stringify(blocks)
            || VX_TRM !== trmBefore;
        if (changed) renderPageBlocksInto(container, blocks);
        vxCacheSet(cacheKey, blocks);
    } catch (e) {
        console.error("Error cargando contenido de la página:", e);
    }
}

function renderPageBlocksInto(container, blocks) {
    container.innerHTML = blocks
        .filter(b => b.is_visible)
        .map(b => renderPageBlock(b))
        .join("\n");

    container.querySelectorAll("script").forEach(oldScript => {
        const newScript = document.createElement("script");
        for (const attr of oldScript.attributes) {
            newScript.setAttribute(attr.name, attr.value);
        }
        newScript.textContent = oldScript.textContent;
        oldScript.parentNode.replaceChild(newScript, oldScript);
    });

    // El footer (con el toggle de moneda) se inyecta recién arriba, hay que sincronizarlo
    updateCurrencyToggle();
}

function renderPageBlock(block) {
    const c = block.config;
    switch (block.block_type) {
        case "content_hero":
            return `<section class="hero">
                ${c.eyebrow ? `<p class="hero-eyebrow">${c.eyebrow}</p>` : ""}
                <h1>${c.title_html || ""}</h1>
                <div class="hero-cut"></div>
                ${c.text ? `<p>${c.text}</p>` : ""}
            </section>`;

        case "custom_html":
            return `<style>${c.css || ""}</style>${c.html || ""}`;

        case "footer":
            return `<footer>
                <div class="footer-top">
                    <div>
                        <div class="footer-logo"><span class="a">Velo</span><span class="b">nox</span></div>
                        <p class="footer-tagline">${c.tagline || ""}</p>
                    </div>
                    <div class="footer-col"><p>Tienda</p><a href="/catalogo.html">Catálogo</a><a href="/index.html">Sets regalo</a></div>
                    <div class="footer-col"><p>Ayuda</p><a href="/contacto.html">Contáctanos</a><a href="/politicas.html">Políticas</a></div>
                    <div class="footer-col"><p>Legal</p><a href="/terminos.html">Términos y condiciones</a><a href="/politicas.html#privacidad">Privacidad</a></div>
                </div>
                <div class="footer-bottom">
                    <p class="footer-copy">© 2026 ${c.store_name || "Velonox"}. Todos los derechos reservados.</p>
                    <div style="display:flex;align-items:center;gap:1rem">
                        <div style="display:flex;align-items:center;background:#1A2820;border:1px solid #2A4A38;border-radius:2px;overflow:hidden">
                            <button id="vx-btn-usd" onclick="setCurrency('USD')"
                                style="padding:4px 10px;font-size:11px;font-weight:600;cursor:pointer;border:none;background:transparent;color:#4A6A5A;font-family:'DM Sans',sans-serif;transition:all .2s">
                                USD
                            </button>
                            <button id="vx-btn-cop" onclick="setCurrency('COP')"
                                style="padding:4px 10px;font-size:11px;font-weight:600;cursor:pointer;border:none;background:#1D7A4F;color:white;font-family:'DM Sans',sans-serif;transition:all .2s">
                                COP
                            </button>
                        </div>
                        <div class="footer-social"><a href="https://www.instagram.com/velonox__?igsh=MXhsOXhmcjA5MHI3NA%3D%3D&amp;utm_source=qr" target="_blank" rel="noopener"><i class="ti ti-brand-instagram"></i></a><a href="https://www.tiktok.com/@velonox5?_r=1&amp;_t=ZS-98EK8bwblET" target="_blank" rel="noopener"><i class="ti ti-brand-tiktok"></i></a><a href="https://www.facebook.com/share/1EHVcp5a2P/?mibextid=wwXIfr" target="_blank" rel="noopener"><i class="ti ti-brand-facebook"></i></a></div>
                    </div>
                </div>
            </footer>`;

        // Tipos genéricos de la librería de bloques, por si el admin los añade aquí
        case "announcement_bar":
            return `<div style="background:${c.background_color || "#1D7A4F"};color:${c.text_color || "#fff"};text-align:center;padding:0.5rem 1rem;font-size:12px;font-weight:500;letter-spacing:.3px">${c.text || ""}</div>`;

        case "text_section":
            return `<section style="background:${c.background_color || "#F5F5F3"};padding:3.5rem 2rem;text-align:${c.text_align || "center"}">
                <h2 style="font-family:'Playfair Display',serif;font-size:28px;font-weight:700;color:#0F1A14;margin-bottom:1rem">${c.title || ""}</h2>
                <p style="font-size:15px;color:#6B8A7A;max-width:600px;margin:0 auto;line-height:1.7">${c.content || ""}</p>
            </section>`;

        case "image_banner":
            if (!c.image_url) return "";
            return `<div style="width:100%;height:${c.height || 300}px;overflow:hidden"><img src="${c.image_url}" alt="${c.alt_text || ""}" style="width:100%;height:100%;object-fit:cover"></div>`;

        case "testimonials": {
            const items = c.items || [];
            return `<section style="background:#F5F5F3;padding:3.5rem 2rem">
                <div style="margin-bottom:2rem"><h2 style="font-family:'Playfair Display',serif;font-size:28px;font-weight:700;color:#0F1A14">${c.title || ""}</h2></div>
                <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:1rem">
                    ${items.map(item => `
                    <div style="background:white;border:1px solid #E8E8E4;border-radius:2px;padding:1.2rem">
                        <div style="color:#D6C5A0;margin-bottom:.5rem;font-size:13px">${"★".repeat(item.rating || 5)}</div>
                        <p style="color:#4A6A5A;font-size:13px;margin-bottom:.7rem;line-height:1.6">"${item.text || ""}"</p>
                        <strong style="font-size:12px;color:#0F1A14">— ${item.name || ""}</strong>
                    </div>`).join("")}
                </div>
            </section>`;
        }

        case "categories": {
            const cats = c.items || [];
            return `<section style="padding:3.5rem 2rem">
                <div style="margin-bottom:2rem"><h2 style="font-family:'Playfair Display',serif;font-size:28px;font-weight:700;color:#0F1A14">${c.title || ""}</h2></div>
                <div class="cat-grid">
                    ${cats.map(cat => `
                    <div class="cat-card">
                        <div class="cat-icon"><i class="ti ti-tools-kitchen-2"></i></div>
                        <p class="cat-name">${cat}</p>
                    </div>`).join("")}
                </div>
            </section>`;
        }

        default:
            return "";
    }
}
