/**
 * Velonox — Widget de Chat
 * -------------------------------------------------
 * Cómo usarlo: agrega esta línea antes de </body> en cualquier
 * página de velonox.co:
 *
 *   <script src="/js/velonox-chat-widget.js"></script>
 *
 * No requiere ninguna otra dependencia. Se auto-inicializa.
 */
(function () {
  "use strict";

  // ---------------------------------------------------------
  // Configuración
  // ---------------------------------------------------------
  var CONFIG = {
    webhookUrl: "https://n8n-production-20ba9.up.railway.app/webhook/Velonox_path",
    welcomeMessage: "Hola, soy el asistente de Velonox. Puedo ayudarte a elegir tu próxima olla o sartén, revisar el estado de tu pedido, o resolver dudas sobre el acero inoxidable. ¿En qué te ayudo?",
    storageKey: "velonox_chat_session_id"
  };

  // ---------------------------------------------------------
  // session_id persistente por visitante (sobrevive recargas,
  // vive en localStorage del navegador del cliente)
  // ---------------------------------------------------------
  function getSessionId() {
    try {
      var existing = window.localStorage.getItem(CONFIG.storageKey);
      if (existing) return existing;
      var fresh = "vlx-" + Date.now() + "-" + Math.random().toString(36).slice(2, 10);
      window.localStorage.setItem(CONFIG.storageKey, fresh);
      return fresh;
    } catch (e) {
      // Si localStorage no está disponible (modo incógnito estricto, etc.)
      return "vlx-" + Date.now() + "-" + Math.random().toString(36).slice(2, 10);
    }
  }

  var sessionId = getSessionId();

  // ---------------------------------------------------------
  // Estilos — tokens tomados de la guía de marca Velonox
  // ---------------------------------------------------------
  var css = "\n" +
    "#vlx-chat-root {\n" +
    "  --vlx-noche: #0F1A14;\n" +
    "  --vlx-verde: #1D7A4F;\n" +
    "  --vlx-salvia: #C8D8C0;\n" +
    "  --vlx-arena: #D6C5A0;\n" +
    "  --vlx-hueso: #F5F5F3;\n" +
    "  --vlx-acero: #B0BEB8;\n" +
    "  font-family: 'DM Sans', Arial, sans-serif;\n" +
    "  position: fixed;\n" +
    "  z-index: 999999;\n" +
    "  bottom: 24px;\n" +
    "  right: 24px;\n" +
    "}\n" +
    "#vlx-chat-root * { box-sizing: border-box; }\n" +
    "#vlx-bubble {\n" +
    "  width: 60px; height: 60px; border-radius: 50%;\n" +
    "  background: var(--vlx-noche);\n" +
    "  border: 1px solid var(--vlx-verde);\n" +
    "  display: flex; align-items: center; justify-content: center;\n" +
    "  cursor: pointer;\n" +
    "  box-shadow: 0 8px 24px rgba(15,26,20,0.35);\n" +
    "  transition: transform .18s ease;\n" +
    "}\n" +
    "#vlx-bubble:hover { transform: scale(1.06); }\n" +
    "#vlx-bubble svg { width: 26px; height: 26px; }\n" +
    "#vlx-badge {\n" +
    "  position: absolute; top: -2px; right: -2px;\n" +
    "  width: 12px; height: 12px; border-radius: 50%;\n" +
    "  background: var(--vlx-verde); border: 2px solid var(--vlx-hueso);\n" +
    "  display: none;\n" +
    "}\n" +
    "#vlx-panel {\n" +
    "  position: absolute; bottom: 76px; right: 0;\n" +
    "  width: 360px; max-width: calc(100vw - 32px);\n" +
    "  height: 520px; max-height: 70vh;\n" +
    "  background: var(--vlx-hueso);\n" +
    "  border-radius: 16px;\n" +
    "  box-shadow: 0 20px 60px rgba(15,26,20,0.28);\n" +
    "  display: none;\n" +
    "  flex-direction: column;\n" +
    "  overflow: hidden;\n" +
    "  border: 1px solid #E8E8E4;\n" +
    "}\n" +
    "#vlx-panel.vlx-open { display: flex; }\n" +
    "#vlx-header {\n" +
    "  background: var(--vlx-noche);\n" +
    "  padding: 16px 18px;\n" +
    "  display: flex; align-items: center; justify-content: space-between;\n" +
    "  flex-shrink: 0;\n" +
    "}\n" +
    "#vlx-header-title {\n" +
    "  font-family: 'Playfair Display', Georgia, serif;\n" +
    "  color: var(--vlx-hueso);\n" +
    "  font-size: 18px; font-weight: 700; letter-spacing: -.3px;\n" +
    "}\n" +
    "#vlx-header-title span { color: var(--vlx-salvia); }\n" +
    "#vlx-header-sub {\n" +
    "  color: var(--vlx-acero); font-size: 11px; letter-spacing: 1px;\n" +
    "  text-transform: uppercase; margin-top: 2px;\n" +
    "}\n" +
    "#vlx-close {\n" +
    "  background: none; border: none; cursor: pointer;\n" +
    "  color: var(--vlx-salvia); font-size: 20px; line-height: 1;\n" +
    "  padding: 4px;\n" +
    "}\n" +
    "#vlx-messages {\n" +
    "  flex: 1; overflow-y: auto; padding: 16px;\n" +
    "  display: flex; flex-direction: column; gap: 10px;\n" +
    "  background: var(--vlx-hueso);\n" +
    "}\n" +
    "#vlx-messages::-webkit-scrollbar { width: 6px; }\n" +
    "#vlx-messages::-webkit-scrollbar-thumb { background: var(--vlx-acero); border-radius: 3px; }\n" +
    ".vlx-msg {\n" +
    "  max-width: 82%; padding: 10px 13px; border-radius: 12px;\n" +
    "  font-size: 13.5px; line-height: 1.5; white-space: pre-wrap;\n" +
    "}\n" +
    ".vlx-msg-bot {\n" +
    "  align-self: flex-start;\n" +
    "  background: #fff; color: var(--vlx-noche);\n" +
    "  border: 1px solid #E8E8E4;\n" +
    "  border-bottom-left-radius: 3px;\n" +
    "}\n" +
    ".vlx-msg-user {\n" +
    "  align-self: flex-end;\n" +
    "  background: var(--vlx-verde); color: #fff;\n" +
    "  border-bottom-right-radius: 3px;\n" +
    "}\n" +
    ".vlx-msg-typing {\n" +
    "  align-self: flex-start;\n" +
    "  background: #fff; border: 1px solid #E8E8E4;\n" +
    "  padding: 12px 14px; border-radius: 12px; border-bottom-left-radius: 3px;\n" +
    "  display: flex; gap: 4px;\n" +
    "}\n" +
    ".vlx-dot {\n" +
    "  width: 6px; height: 6px; border-radius: 50%; background: var(--vlx-acero);\n" +
    "  animation: vlx-bounce 1.2s infinite ease-in-out;\n" +
    "}\n" +
    ".vlx-dot:nth-child(2) { animation-delay: .15s; }\n" +
    ".vlx-dot:nth-child(3) { animation-delay: .3s; }\n" +
    "@keyframes vlx-bounce { 0%, 60%, 100% { opacity: .35; transform: translateY(0); } 30% { opacity: 1; transform: translateY(-3px); } }\n" +
    "#vlx-input-row {\n" +
    "  display: flex; gap: 8px; padding: 12px;\n" +
    "  border-top: 1px solid #E8E8E4; background: #fff; flex-shrink: 0;\n" +
    "}\n" +
    "#vlx-input {\n" +
    "  flex: 1; border: 1px solid #E8E8E4; border-radius: 10px;\n" +
    "  padding: 10px 12px; font-size: 13.5px; font-family: inherit;\n" +
    "  color: var(--vlx-noche); resize: none; outline: none;\n" +
    "  max-height: 80px;\n" +
    "}\n" +
    "#vlx-input:focus { border-color: var(--vlx-verde); }\n" +
    "#vlx-send {\n" +
    "  background: var(--vlx-verde); border: none; border-radius: 10px;\n" +
    "  width: 40px; flex-shrink: 0; cursor: pointer;\n" +
    "  display: flex; align-items: center; justify-content: center;\n" +
    "  transition: opacity .15s ease;\n" +
    "}\n" +
    "#vlx-send:disabled { opacity: .5; cursor: default; }\n" +
    "#vlx-send svg { width: 16px; height: 16px; }\n" +
    "@media (max-width: 480px) {\n" +
    "  #vlx-chat-root { right: 12px; bottom: 12px; }\n" +
    // En móvil el panel pasa a ser pantalla completa en vez de la cajita flotante
    // 360x520: así no hay "hueco" fijo que el teclado táctil pueda tapar. El alto
    // real (que descuenta el teclado) lo termina de ajustar JS vía visualViewport,
    // porque 100dvh no reacciona al teclado en todos los navegadores (Safari iOS).
    "  #vlx-panel {\n" +
    "    position: fixed;\n" +
    "    top: 0; left: 0; right: 0; bottom: auto;\n" +
    "    max-width: none;\n" +
    "    border-radius: 0;\n" +
    "    height: 100vh; max-height: 100vh;\n" +
    "    height: 100dvh; max-height: 100dvh;\n" +
    "  }\n" +
    "}\n";

  var styleTag = document.createElement("style");
  styleTag.textContent = css;
  document.head.appendChild(styleTag);

  // ---------------------------------------------------------
  // Marcado (HTML)
  // ---------------------------------------------------------
  var root = document.createElement("div");
  root.id = "vlx-chat-root";
  root.innerHTML =
    '<div id="vlx-panel">' +
    '  <div id="vlx-header">' +
    "    <div>" +
    '      <div id="vlx-header-title">Velo<span>nox</span></div>' +
    '      <div id="vlx-header-sub">Cocina de por vida</div>' +
    "    </div>" +
    '    <button id="vlx-close" aria-label="Cerrar chat">&times;</button>' +
    "  </div>" +
    '  <div id="vlx-messages"></div>' +
    '  <div id="vlx-input-row">' +
    '    <textarea id="vlx-input" rows="1" placeholder="Escribe tu mensaje..." aria-label="Mensaje"></textarea>' +
    '    <button id="vlx-send" aria-label="Enviar">' +
    '      <svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>' +
    "    </button>" +
    "  </div>" +
    "</div>" +
    '<div id="vlx-bubble" role="button" aria-label="Abrir chat">' +
    '  <span id="vlx-badge"></span>' +
    '  <svg viewBox="0 0 24 24" fill="none" stroke="#C8D8C0" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>' +
    "</div>";
  document.body.appendChild(root);

  var panel = document.getElementById("vlx-panel");
  var bubble = document.getElementById("vlx-bubble");
  var badge = document.getElementById("vlx-badge");
  var closeBtn = document.getElementById("vlx-close");
  var messagesEl = document.getElementById("vlx-messages");
  var input = document.getElementById("vlx-input");
  var sendBtn = document.getElementById("vlx-send");

  var hasOpened = false;
  var isSending = false;

  // ---------------------------------------------------------
  // Helpers de UI
  // ---------------------------------------------------------
  function appendMessage(text, who) {
    var el = document.createElement("div");
    el.className = "vlx-msg " + (who === "user" ? "vlx-msg-user" : "vlx-msg-bot");
    el.textContent = text;
    messagesEl.appendChild(el);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return el;
  }

  function showTyping() {
    var el = document.createElement("div");
    el.className = "vlx-msg-typing";
    el.id = "vlx-typing";
    el.innerHTML = '<span class="vlx-dot"></span><span class="vlx-dot"></span><span class="vlx-dot"></span>';
    messagesEl.appendChild(el);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function hideTyping() {
    var el = document.getElementById("vlx-typing");
    if (el) el.remove();
  }

  function autoResize() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 80) + "px";
  }

  // ---------------------------------------------------------
  // Alto real en móvil (descuenta el teclado táctil)
  // ---------------------------------------------------------
  // position:fixed + vh/dvh no siempre se recalculan cuando el teclado abre
  // (sobre todo en Safari iOS), porque se miden contra el viewport de layout,
  // no el visual. window.visualViewport sí refleja el alto visible real, así
  // que lo usamos para fijar el alto/posición del panel por JS mientras está
  // abierto en móvil; en desktop se limpian los estilos inline y manda el CSS.
  function isMobile() {
    return window.matchMedia("(max-width: 480px)").matches;
  }

  function syncMobileViewport() {
    if (isMobile() && panel.classList.contains("vlx-open") && window.visualViewport) {
      var vv = window.visualViewport;
      panel.style.height = vv.height + "px";
      panel.style.top = vv.offsetTop + "px";
    } else {
      panel.style.height = "";
      panel.style.top = "";
    }
  }

  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", syncMobileViewport);
    window.visualViewport.addEventListener("scroll", syncMobileViewport);
  }
  window.addEventListener("resize", syncMobileViewport);

  // ---------------------------------------------------------
  // Comunicación con n8n
  // ---------------------------------------------------------
  function sendMessage() {
    var text = input.value.trim();
    if (!text || isSending) return;

    appendMessage(text, "user");
    input.value = "";
    autoResize();
    isSending = true;
    sendBtn.disabled = true;
    showTyping();

    fetch(CONFIG.webhookUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, session_id: sessionId })
    })
      .then(function (res) {
        if (!res.ok) throw new Error("Respuesta no válida del servidor");
        return res.json();
      })
      .then(function (data) {
        hideTyping();
        var reply = (data && data.reply) ? data.reply : "Lo siento, no pude procesar tu mensaje. ¿Puedes intentar de nuevo?";
        appendMessage(reply, "bot");
      })
      .catch(function () {
        hideTyping();
        appendMessage("Hubo un problema de conexión. Intenta de nuevo en un momento, o escríbenos a ayuda@velonox.co.", "bot");
      })
      .finally(function () {
        isSending = false;
        sendBtn.disabled = false;
      });
  }

  // ---------------------------------------------------------
  // Eventos
  // ---------------------------------------------------------
  bubble.addEventListener("click", function () {
    var opening = !panel.classList.contains("vlx-open");
    panel.classList.toggle("vlx-open");
    if (opening) {
      badge.style.display = "none";
      syncMobileViewport();
      if (!hasOpened) {
        hasOpened = true;
        appendMessage(CONFIG.welcomeMessage, "bot");
      }
      // En móvil no forzamos el foco: abrir el teclado de una vez, mientras el
      // panel todavía se está desplegando, es lo que causaba el salto de layout
      // que tapaba el primer mensaje. Que el usuario abra el teclado al tocar
      // el campo, ya con el panel asentado.
      if (!isMobile()) {
        input.focus();
      }
    } else {
      syncMobileViewport();
    }
  });

  closeBtn.addEventListener("click", function () {
    panel.classList.remove("vlx-open");
    syncMobileViewport();
  });

  sendBtn.addEventListener("click", sendMessage);

  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  input.addEventListener("input", autoResize);
})();
