const API_URL = "https://velonox.onrender.com";

// ─── TOKEN ───────────────────────────────────────────────────────────────────

function getToken() {
    return localStorage.getItem("token");
}

function setToken(token) {
    localStorage.setItem("token", token);
}

function removeToken() {
    localStorage.removeItem("token");
}

function isLoggedIn() {
    return !!getToken();
}

// ─── FETCH BASE ───────────────────────────────────────────────────────────────

async function apiFetch(endpoint, options = {}) {
    const token = getToken();
    // Content-Type solo cuando hay body: en un GET convierte la petición en
    // "no simple" y el navegador hace un preflight CORS extra (~0.5s más por carga).
    const headers = {};
    if (options.body) headers["Content-Type"] = "application/json";
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const response = await fetch(`${API_URL}${endpoint}`, {
        ...options,
        headers: { ...headers, ...options.headers }
    });

    if (response.status === 401 && token) {
        // Solo redirige si ya había un token (sesión expirada/inválida). Un 401
        // sin token (ej. login con credenciales incorrectas) no es una sesión
        // que expiró, así que debe caer al throw de abajo en vez de recargar.
        removeToken();
        window.location.href = "/login.html";
        return;
    }

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Error en la solicitud");
    }

    if (response.status === 204) return null;
    return response.json();
}

// ─── AUTH ─────────────────────────────────────────────────────────────────────


async function register(email, password, fullName) {
    return apiFetch("/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password, full_name: fullName })
    });
}

async function login(email, password) {
    const data = await apiFetch("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password })
    });
    setToken(data.access_token);
    return data;
}

async function forgotPassword(email) {
    return apiFetch("/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify({ email })
    });
}

async function resetPassword(token, newPassword) {
    return apiFetch("/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({ token, new_password: newPassword })
    });
}

async function getMe() {
    return apiFetch("/auth/me");
}

function logout() {
    removeToken();
    window.location.href = "/login.html";
}

// ─── PRODUCTOS ────────────────────────────────────────────────────────────────

async function getProducts() {
    return apiFetch("/products/");
}

async function getProduct(id) {
    return apiFetch(`/products/${id}`);
}

async function createProduct(data) {
    return apiFetch("/products/", { method: "POST", body: JSON.stringify(data) });
}

async function updateProduct(id, data) {
    return apiFetch(`/products/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

async function deleteProduct(id) {
    return apiFetch(`/products/${id}`, { method: "DELETE" });
}


// ─── PÁGINAS DE PRODUCTO ──────────────────────────────────────────────────────

async function getProductPage(productId) {
    return apiFetch(`/product-pages/${productId}`);
}

async function updateProductPage(productId, data) {
    return apiFetch(`/product-pages/${productId}`, {
        method: "PUT",
        body: JSON.stringify(data)
    });
}

async function resetProductPage(productId) {
    return apiFetch(`/product-pages/${productId}`, { method: "DELETE" });
}

// ─── CARRITO ──────────────────────────────────────────────────────────────────

async function getCart() {
    return apiFetch("/cart/");
}

async function addToCart(productId, quantity = 1) {
    return apiFetch("/cart/items", {
        method: "POST",
        body: JSON.stringify({ product_id: productId, quantity })
    });
}

async function updateCartItem(itemId, quantity) {
    return apiFetch(`/cart/items/${itemId}`, {
        method: "PUT",
        body: JSON.stringify({ quantity })
    });
}

async function removeFromCart(itemId) {
    return apiFetch(`/cart/items/${itemId}`, { method: "DELETE" });
}

// ─── PAGOS Y ÓRDENES ─────────────────────────────────────────────────────────

async function checkout(data) {
    return apiFetch("/payments/checkout", { method: "POST", body: JSON.stringify(data) });
}

async function getOrders() {
    return apiFetch("/payments/orders");
}

async function getOrder(orderId) {
    return apiFetch(`/payments/orders/${orderId}`);
}

// ─── CARRITO DE INVITADO (localStorage) ──────────────────────────────────────

function getGuestCart() {
    try {
        return JSON.parse(localStorage.getItem("velonox_cart") || "[]");
    } catch(e) { return []; }
}

function saveGuestCart(items) {
    localStorage.setItem("velonox_cart", JSON.stringify(items));
}

function addToGuestCart(product) {
    const cart = getGuestCart();
    const existing = cart.find(i => i.id === product.id);
    if (existing) {
        existing.quantity += 1;
    } else {
        cart.push({
            id: product.id,
            name: product.name,
            price: product.price,
            image_url: product.image_url,
            stock: product.stock,
            quantity: 1
        });
    }
    saveGuestCart(cart);
}

function removeFromGuestCart(productId) {
    const cart = getGuestCart().filter(i => i.id !== productId);
    saveGuestCart(cart);
}

function updateGuestCartItem(productId, quantity) {
    const cart = getGuestCart();
    const item = cart.find(i => i.id === productId);
    if (item) {
        if (quantity <= 0) {
            removeFromGuestCart(productId);
        } else {
            item.quantity = quantity;
            saveGuestCart(cart);
        }
    }
}

function clearGuestCart() {
    localStorage.removeItem("velonox_cart");
}

function getGuestCartTotal() {
    return getGuestCart().reduce((sum, i) => sum + i.price * i.quantity, 0);
}

// Checkout de invitado
async function guestCheckout(data) {
    return apiFetch("/guest/checkout", {
        method: "POST",
        body: JSON.stringify(data)
    });
}

// ─── SISTEMA DE MONEDA ────────────────────────────────────────────────────────

const VX_CURRENCY_KEY = "velonox_currency";
const VX_TRM_KEY = "velonox_trm";
// Arranca con la última TRM conocida (si la hay) para poder pintar precios
// antes de que responda el backend; loadTRM() la actualiza después.
let VX_TRM = parseFloat(vxStorageGet(VX_TRM_KEY)) || 4200;
let VX_CURRENCY = localStorage.getItem(VX_CURRENCY_KEY) || "COP";

// Cargar TRM desde el backend al iniciar
async function loadTRM() {
    try {
        const res = await fetch(`${API_URL}/settings/trm`);
        const data = await res.json();
        if (data.trm) {
            VX_TRM = data.trm;
            vxStorageSet(VX_TRM_KEY, String(VX_TRM));
        }
    } catch(e) {
        // sin red: se queda con la última TRM conocida (o 4200 por defecto)
    }
}

// ─── CACHÉ LOCAL DE CONTENIDO ─────────────────────────────────────────────────
// Guarda la última versión de bloques/productos de cada página para pintarla al
// instante en visitas repetidas mientras llega la versión fresca del backend
// (el plan gratis de Render tarda ~0.5s por petición). Si localStorage no está
// disponible (modo privado, bloqueado), simplemente no hay caché.
function vxStorageGet(key) {
    try { return localStorage.getItem(key); } catch(e) { return null; }
}
function vxStorageSet(key, value) {
    try { localStorage.setItem(key, value); } catch(e) {}
}
function vxCacheGet(key) {
    try { return JSON.parse(vxStorageGet("vx_cache_" + key)); } catch(e) { return null; }
}
function vxCacheSet(key, value) {
    vxStorageSet("vx_cache_" + key, JSON.stringify(value));
}

// ─── PRE-CARGA DE PETICIONES ──────────────────────────────────────────────────
// vxPrefetch(url) lanza el GET de inmediato (p. ej. al inicio de init(), en
// paralelo con el layout) y vxTakePrefetched(url) entrega esa misma respuesta
// después a quien la necesite. Cada pre-carga se consume una sola vez; si no
// hubo pre-carga, vxTakePrefetched hace un fetch normal.
const _vxPrefetched = {};
function vxPrefetch(url) {
    if (!_vxPrefetched[url]) _vxPrefetched[url] = fetch(url);
    return _vxPrefetched[url];
}
function vxTakePrefetched(url) {
    const p = _vxPrefetched[url];
    delete _vxPrefetched[url];
    return p || fetch(url);
}

// Formatear precio según moneda activa
function vxPrice(usdAmount) {
    if (VX_CURRENCY === "COP") {
        const cop = Math.round(usdAmount * VX_TRM);
        return "$" + cop.toLocaleString("es-CO") + " COP";
    }
    return "$" + parseFloat(usdAmount).toFixed(2) + " USD";
}

// Cambiar moneda y recargar precios en la página
function setCurrency(currency) {
    VX_CURRENCY = currency;
    localStorage.setItem(VX_CURRENCY_KEY, currency);
    // Dispara evento para que cada página actualice sus precios
    window.dispatchEvent(new CustomEvent("currencyChanged", { detail: { currency } }));
    // Actualizar visual del toggle
    updateCurrencyToggle();
}

function getCurrency() {
    return VX_CURRENCY;
}

function updateCurrencyToggle() {
    const btnUSD = document.getElementById("vx-btn-usd");
    const btnCOP = document.getElementById("vx-btn-cop");
    if (!btnUSD || !btnCOP) return;
    if (VX_CURRENCY === "USD") {
        btnUSD.style.background = "#1D7A4F";
        btnUSD.style.color = "white";
        btnCOP.style.background = "transparent";
        btnCOP.style.color = "#4A6A5A";
    } else {
        btnCOP.style.background = "#1D7A4F";
        btnCOP.style.color = "white";
        btnUSD.style.background = "transparent";
        btnUSD.style.color = "#4A6A5A";
    }
}