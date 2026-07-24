# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Velonox — an e-commerce store. FastAPI backend (Railway) + PostgreSQL, vanilla HTML/CSS/JS frontend (Cloudflare Pages, `e-commerce-con-fastapi-y-postgreqsl.pages.dev`), no build step or framework on either side.

## Commands

Backend (run from `backend/`):
```
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload
```
- Create a migration: `alembic revision --autogenerate -m "descripcion"` (from `backend/`, engine must be reachable via `DATABASE_URL`).
- Apply migrations: `alembic upgrade head`.
- Production start command (see `backend/procfile`): `alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT`.
- There is no test suite in this repo — do not assume `pytest` or similar is configured.

Frontend: static files under `frontend/`, no build/bundle step. Serve the directory with any static server (e.g. VS Code Live Server on port 5500, matched by the backend's CORS allow-list) and open the `.html` files directly.

## Architecture

### Backend (`backend/`)
Sync SQLAlchemy 2.x (`database.py`) — **do not** introduce async ORM calls without migrating the whole project consistently; this is a deliberate convention, not an oversight.

- `models/` — `User`, `Product`, `Cart`, `Order`, `StoreLayout`, `StoreSetting`, `ProductPage`, `Category`, `PasswordResetToken`, `ProductVariant`, `ProductImage`.
- `routes/` — one router per domain: `auth`, `products`, `product_variants`, `product_images`, `categories`, `cart`, `payments`, `layout`, `product_pages`, `metrics`, `settings`, `guest_checkout`. All mounted in `main.py`. `product_variants` and `product_images` share the `/products` prefix (`routes/products.py` doesn't own it exclusively — nested paths like `/products/{id}/variants` live in their own files).
- `schemas/` — Pydantic request/response models per domain.
- `services/` — business logic: `auth.py` (JWT), `bold.py` (payment signatures), `dropi.py` (fulfillment), `email.py`, `settings.py` (TRM/currency).
- `middleware/auth.py` — `get_current_user` / `get_current_admin` dependencies (JWT via `python-jose`, hashing via `bcrypt`).
- `alembic/` — migrations; `versions/` holds one file per revision.

**Payments**: uses **Bold** (Colombian gateway, `services/bold.py`, integrity-signature + webhook HMAC verification) and **Dropi** (`services/dropi.py`, order fulfillment/dropshipping) — Stripe is no longer used (kept commented out in `requirements.txt` for history; ignore README/notes mentions of Stripe, they're stale).

**Currency**: store prices are USD internally; `services/settings.py` / the `/settings/trm` endpoint expose the current USD→COP exchange rate (TRM) so the frontend can render either currency.

**CMS-driven layout**: `models/layout.py` (`store_layout` table) + `routes/layout.py`. Pages are built from configurable "blocks" (`announcement_bar`, `hero_banner`, `content_hero`, `product_grid`, `text_section`, `testimonials`, `categories`, `image_banner`, `footer`, `custom_html`, ...) stored per `page_slug`, editable from `frontend/admin.html` and fetched by public pages via `GET /layout/?page=<slug>`. `routes/layout.py` also has an AI block-generation endpoint (Anthropic API, server-side key only). If a `page_slug` has zero rows (first request ever, or after a reset), `GET /layout/` auto-seeds it from `DEFAULT_BLOCKS` (home page) or `CONTENT_PAGE_BLOCKS[slug]` (every other page) and persists that seed — editing those Python dicts only affects pages that get reseeded from scratch, **not** pages that already have rows in the DB; a live page's content has to be fixed via the API/admin (or `/layout/reset`), not by editing the file alone.

**Layout version history**: every `PUT /layout/?page=<slug>` (save) archives the page's pre-save block state into `store_layout_history` (via `_snapshot_current_layout()`) before overwriting it — last `MAX_HISTORY_PER_PAGE` (20) versions kept per page. `GET /layout/history?page=<slug>` lists them, `POST /layout/restore/{history_id}` restores one (itself archiving the current state first, so restoring is undoable too), `POST /layout/reset?page=<slug>` wipes a page's rows so it re-seeds from the defaults above. All three are admin-only and surfaced in `admin.html` via the **Historial** button next to "Guardar cambios". This exists because saves are a destructive full replace with no other backup (`admin.html`'s `saveLayout()` PUTs whatever is in the in-memory `layout` array — the "Guardar cambios" button is disabled and the save call refuses to run while `loadLayout()` is still in flight, via the `isLayoutLoading` flag, since a stale/incomplete `layout` array saved mid-load is what caused a real data-loss incident).

**Product variants & images** (`models/product_variant.py`, `models/product_image.py`, added 2026-07): `products.category` is a loose string match against `Category.slug` — **no FK, no intermediate table**, so a typo or a deleted category silently orphans a product (this predates variants/images but matters for the same area of the schema). `ProductVariant` (name, optional `price` override, `stock`, optional `image_id`) and `ProductImage` (url, `order_index`, `is_primary`) are both scoped to a `product_id` (`ON DELETE CASCADE`) and embedded in `ProductResponse` as `variants: []` / `images: []` so the admin UI gets them for free from `GET /products/`. `Product.image_url` (the original single-image field, still used by every card/grid on the public site) is **not** replaced by the gallery — it's kept in sync automatically: the first image added to a product's gallery, or whichever one is later marked primary via `POST /products/{id}/images/{image_id}/set-primary`, overwrites it. This is why no public-facing page besides `product.html` needed to change when the gallery/variants feature was added.

**Variant ↔ image linking, and what it does *not* do**: `ProductVariant.image_id` (FK to `product_images.id`, `ON DELETE SET NULL`) lets `product.html` swap the displayed photo when a variant button is clicked (`selectVariant()`) — set from the "Imagen" dropdown next to each variant row in `admin.html`. Deliberately, selecting a variant does **not** change the displayed price or the stock indicator, and cart/checkout remain entirely product-level (`cart_items`/`order_items` have no `variant_id`) — a variant's `price`/`stock` are informational-only in the admin today. Showing a variant's price on `product.html` without also wiring it into what Bold actually charges would be a real pricing-correctness bug (customer sees one price, gets charged another), so don't add that without also touching cart/checkout/order schemas end-to-end.

**Legacy, unrelated "variants" field — don't confuse with the above**: `models/product_page.py`'s `ProductPage.variants` (a JSON `Text` column, edited via `routes/product_pages.py`) is a *different*, older, dead concept (size/color option labels for a hand-authored page) with no admin editor ever built for it — it's always `[]` in practice. `product.html` used to render *that* field under a "variantes" label before 2026-07; it now renders the real `product.variants` (the `ProductVariant` list above) instead. If you see `page.variants` referenced anywhere, it's stale/vestigial, not the real variant system.

**Security pattern to preserve** (see `docs/notes/proyecto.md`): never call external APIs (Bold, Dropi, Anthropic, TRM source) directly from the frontend — always proxy through the backend using the server's own `.env` keys. CORS uses explicit methods/headers, never `["*"]`. Internal errors (DB, payment gateway) are never surfaced verbatim to the client — return generic messages instead.

### Frontend (`frontend/`)
No bundler, no framework — plain `.html` files each with inline `<script>`/`<style>`, plus shared helpers in `frontend/js/`. All internal links and asset references (`href`/`src`) use absolute paths (leading `/`, e.g. `/js/api.js`, `/admin.html`) rather than relative ones — keep this convention when adding pages or scripts:
- `js/api.js` — `API_URL`, auth token helpers, `apiFetch()`, and the currency system: `VX_CURRENCY`/`VX_TRM` (from `localStorage` + `/settings/trm`), `vxPrice(usdAmount)`, `setCurrency()`, `getCurrency()`, `updateCurrencyToggle()`. `setCurrency()` dispatches a `currencyChanged` window event — any code rendering a price must listen for it (or re-render) to stay in sync.
- `js/page-blocks.js` — `initPageBlocks(slug)` / `renderPageBlock()`, the shared CMS-block renderer used by contacto/nosotros/politicas/terminos/categorias/catalogo/categoria. Calls `loadTRM()` and `updateCurrencyToggle()` itself before rendering, since the footer (with the USD/COP toggle) is injected dynamically. Re-creates `<script>` elements after `innerHTML` injection so inline scripts in `custom_html` blocks actually execute (`<script>` tags inserted via `innerHTML` are otherwise inert).
- `index.html` has its **own** inline block renderer (`renderLayoutBlock()` / `loadLayoutBlocks()`) instead of using `page-blocks.js` — historically a source of drift between the home page and every other content page; check both when touching CMS block rendering.
- `css/product-card.css` — the one shared stylesheet in this otherwise inline-`<style>`-per-page codebase. Fixes the `.prod-grid`/`.prod-card` product grid responsively (2 columns on mobile, title line-clamp, stacked price/button) for `index.html`, `catalogo.html`, `categoria.html`, `regalos.html`. Linked via `<link>` *after* each page's own `<style>` block specifically so it wins the cascade over that page's conflicting breakpoint rules without having to edit them — if adding a page that reuses `.prod-card`, link this file the same way instead of copying the fix inline.

**`catalogo.html` / `categoria.html` naming vs. backend slug** (renamed 2026-07 — `tienda.html` no longer exists): `catalogo.html` is the real full catalog (all products, search/filter/sort) — it's the old `tienda.html`, moved here because that's the name every "Catálogo" link on the site actually expects. `categoria.html` is the single-category view (requires `?cat=<slug>`, redirects to `/categorias.html` without one) — it's the old `catalogo.html`. Neither file's internal `initPageBlocks(...)` call nor its backend `page_slug` were renamed to match — `catalogo.html` still fetches CMS content for slug `"tienda"`, `categoria.html` still fetches slug `"catalogo"` (see `CONTENT_PAGE_BLOCKS` in `routes/layout.py` and `EDITABLE_PAGES` in `admin.html`, where the `file:` field is what maps a slug to its current filename). Don't assume filename and CMS slug match on these two pages.

**Admin panel** (`admin.html`): single large file, tab-based SPA (`switchTab()`: Editor/Productos/Métricas/Categorías/Ajustes). The layout editor has a live preview `<iframe id="preview-frame">` driven by `EDITABLE_PAGES` (page key → backend slug + real frontend filename) and `renderPreview()`: for every editable page (including the home page) it fetches the real page file, injects the in-memory (possibly unsaved) block edits into its `#layout-container`, and loads the result via `iframe.srcdoc` — this keeps the preview byte-identical to production instead of a hand-maintained mock. The preview neutralizes the real page's hidden `#nav-admin` link (it would otherwise be visible, since the iframe shares the admin's login session, and could navigate the iframe into `admin.html` itself). Pages not in `EDITABLE_PAGES` (cart/login/product/checkout, etc.) are "preview-only" and load via real `iframe.src` navigation instead.

**Category `<select>` in the product form**: `#p-category` used to be hardcoded `<option>`s copy-pasted from `DEFAULT_CATEGORIES` (`routes/categories.py`) — creating/renaming a category never showed up there even after a hard refresh, because nothing ever fetched `/categories/` for it. Fixed 2026-07 via `loadProductCategoryOptions()`, called on `init()`, on switching to the "Productos" tab, and after `handleSaveCat()` — if you add another way to create/edit categories, call it there too. Note there is still no "create category" button in the UI (`handleSaveCat()` only does `PUT /categories/{slug}` on an existing one, even though `POST /categories/` exists on the backend) — new categories currently have to be created via direct API call.

**Variants/gallery editor**: the "Variantes" and "Galería" panels below the product form (`#variants-section` / `#images-section`) only render once you click "Editar" on an *existing* product (`handleEditProduct()`) — a variant or a gallery image needs a real `product_id` to attach to, so they're hidden for "Nuevo producto". Both keep a local cache (`currentVariants`/`currentImages`) synced back into `previewProducts` after every add/update/delete (`syncVariantsToPreviewCache()`/`syncImagesToPreviewCache()`) so reopening the editor for the same product without a full page reload shows fresh data. Deleting a gallery image that a variant was linked to sets that variant's `image_id` to `null` server-side (FK `ON DELETE SET NULL`) and the admin JS mirrors that locally in the same handler.

**`</script>` escaping gotcha**: several places build HTML strings containing literal `<script>...</script>` inside a JS template literal that itself lives inside another `<script>` block (e.g. `admin.html`'s preview generation). The literal byte sequence `</script>` (case-insensitive) closes the *enclosing* script tag as far as the HTML parser is concerned, regardless of JS string context — always escape as `<\/script>` in these cases (existing precedent throughout `admin.html`).

**Nav-admin pattern**: every public page has a hidden `<a id="nav-admin" href="/admin.html" style="display:none">` shown only when `getMe().is_admin` is true. Keep this consistent (correct `/` path, matching id) across all pages.

## Deployment

Backend: Railway (`backend/procfile` runs migrations then `uvicorn`). Frontend: Cloudflare Pages, static (`frontend/_redirects` has a catch-all 404 rule, no SPA fallback to any page). Cloudflare Web Analytics is embedded in the frontend pages.

## Idiome
Spanish
