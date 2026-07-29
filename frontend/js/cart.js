// ─── BADGE DEL CARRITO (barra de navegación) ───────────────────────────────────
// El conteo se basa en el carrito de invitado de js/api.js (getGuestCart), que es
// la misma fuente que usan cart.html y las demás páginas — así el badge nunca
// queda desincronizado de lo que realmente se ve al entrar al carrito.

function cartCount() {
    return getGuestCart().reduce((sum, i) => sum + (i.quantity || 0), 0);
}

// Actualiza el globo del carrito en la barra de navegación (si existe)
function updateCartBadge() {
    const badge = document.getElementById("cart-badge");
    if (!badge) return;
    const n = cartCount();
    badge.textContent = n;
    badge.style.display = n > 0 ? "flex" : "none";
}
