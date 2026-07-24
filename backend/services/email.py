import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAILS_FROM = os.getenv("EMAILS_FROM", "Velonox <hola@velonox.co>")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://velonox.co")


def send_email(to: str, subject: str, html: str):
    """Envía un email HTML via SMTP."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = EMAILS_FROM
        msg["To"] = to
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to, msg.as_string())
        return True
    except Exception as e:
        print(f"Error enviando email a {to}: {e}")
        return False


def email_bienvenida(to: str, nombre: str, password_temp: str):
    """Email de bienvenida con credenciales cuando se crea cuenta automáticamente."""
    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background:#F5F5F3;font-family:'DM Sans',Arial,sans-serif">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td align="center" style="padding:40px 20px">
          <table width="560" cellpadding="0" cellspacing="0" style="background:white;border-radius:4px;overflow:hidden">

            <!-- Header -->
            <tr><td style="background:#0F1A14;padding:32px 40px;text-align:center">
              <span style="font-size:26px;font-weight:900;color:#C8D8C0;font-family:Georgia,serif">Velo</span>
              <span style="font-size:26px;font-weight:900;color:#1D7A4F;font-family:Georgia,serif">nox</span>
            </td></tr>

            <!-- Body -->
            <tr><td style="padding:40px">
              <p style="font-size:13px;font-weight:500;letter-spacing:3px;color:#1D7A4F;text-transform:uppercase;margin:0 0 12px">Bienvenido a Velonox</p>
              <h1 style="font-family:Georgia,serif;font-size:28px;font-weight:700;color:#0F1A14;margin:0 0 20px;line-height:1.2">
                Hola {nombre}, tu cuenta<br>fue creada automáticamente.
              </h1>
              <p style="font-size:14px;color:#6B8A7A;line-height:1.7;margin:0 0 24px">
                Al completar tu compra, creamos una cuenta Velonox para que puedas hacer seguimiento de tus pedidos, ver tu historial y gestionar tus datos fácilmente.
              </p>

              <!-- Credenciales -->
              <table width="100%" cellpadding="0" cellspacing="0" style="background:#F5F5F3;border-radius:4px;margin-bottom:24px">
                <tr><td style="padding:20px 24px">
                  <p style="font-size:11px;font-weight:500;letter-spacing:2px;color:#1D7A4F;text-transform:uppercase;margin:0 0 12px">Tus credenciales</p>
                  <p style="font-size:13px;color:#4A6A5A;margin:0 0 6px">Email: <strong style="color:#0F1A14">{to}</strong></p>
                  <p style="font-size:13px;color:#4A6A5A;margin:0">Contraseña temporal: <strong style="color:#0F1A14;font-family:monospace;font-size:15px;background:#E8E8E4;padding:2px 8px;border-radius:2px">{password_temp}</strong></p>
                </td></tr>
              </table>

              <p style="font-size:13px;color:#6B8A7A;margin:0 0 24px">
                Por seguridad, te recomendamos cambiar tu contraseña la próxima vez que ingreses.
              </p>

              <!-- CTA -->
              <table cellpadding="0" cellspacing="0" style="margin-bottom:32px">
                <tr><td style="background:#1D7A4F;border-radius:2px">
                  <a href="{FRONTEND_URL}/login.html" style="display:inline-block;padding:12px 28px;color:white;text-decoration:none;font-size:14px;font-weight:500">
                    Ingresar a mi cuenta →
                  </a>
                </td></tr>
              </table>

              <p style="font-size:12px;color:#B0BEB8;line-height:1.6;margin:0">
                Si no realizaste esta compra o no reconoces esta cuenta, contáctanos por WhatsApp al +57 310 888 7296.
              </p>
            </td></tr>

            <!-- Footer -->
            <tr><td style="background:#0F1A14;padding:24px 40px;text-align:center">
              <p style="font-size:11px;color:#4A6A5A;margin:0">© 2026 Velonox · Cocina de por vida.</p>
            </td></tr>

          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """
    return send_email(to, "Bienvenido a Velonox — Tu cuenta fue creada", html)


def email_confirmacion_orden(to: str, nombre: str, order_id: str, items: list, total: float, metodo: str):
    """Email de confirmación de compra con detalle de la orden."""

    metodo_label = "Pago anticipado (tarjeta)" if metodo == "anticipado" else "Pago contraentrega"
    estado_label = "Pago confirmado ✓" if metodo == "anticipado" else "Pendiente de entrega"

    items_html = ""
    for item in items:
        items_html += f"""
        <tr>
          <td style="padding:10px 0;border-bottom:1px solid #E8E8E4;font-size:13px;color:#0F1A14">{item.get('name','Producto')}</td>
          <td style="padding:10px 0;border-bottom:1px solid #E8E8E4;font-size:13px;color:#6B8A7A;text-align:center">{item.get('quantity',1)}</td>
          <td style="padding:10px 0;border-bottom:1px solid #E8E8E4;font-size:13px;color:#0F1A14;text-align:right">${item.get('unit_price',0):.2f}</td>
        </tr>"""

    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background:#F5F5F3;font-family:'DM Sans',Arial,sans-serif">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td align="center" style="padding:40px 20px">
          <table width="560" cellpadding="0" cellspacing="0" style="background:white;border-radius:4px;overflow:hidden">

            <!-- Header -->
            <tr><td style="background:#0F1A14;padding:32px 40px;text-align:center">
              <span style="font-size:26px;font-weight:900;color:#C8D8C0;font-family:Georgia,serif">Velo</span>
              <span style="font-size:26px;font-weight:900;color:#1D7A4F;font-family:Georgia,serif">nox</span>
              <p style="font-size:12px;color:#4A6A5A;margin:8px 0 0">Confirmación de pedido</p>
            </td></tr>

            <!-- Body -->
            <tr><td style="padding:40px">
              <p style="font-size:13px;font-weight:500;letter-spacing:3px;color:#1D7A4F;text-transform:uppercase;margin:0 0 12px">¡Gracias por tu compra!</p>
              <h1 style="font-family:Georgia,serif;font-size:26px;font-weight:700;color:#0F1A14;margin:0 0 8px;line-height:1.2">
                Tu pedido está en camino, {nombre}.
              </h1>
              <p style="font-size:13px;color:#B0BEB8;margin:0 0 28px">Pedido #{order_id[:8].upper()}</p>

              <!-- Estado -->
              <table width="100%" cellpadding="0" cellspacing="0" style="background:#F0FAF5;border:1px solid #A8D8BC;border-radius:4px;margin-bottom:28px">
                <tr><td style="padding:16px 20px">
                  <p style="font-size:12px;font-weight:500;color:#1D7A4F;text-transform:uppercase;letter-spacing:2px;margin:0 0 4px">Estado del pedido</p>
                  <p style="font-size:14px;font-weight:600;color:#0F3A20;margin:0">{estado_label}</p>
                  <p style="font-size:12px;color:#4A6A5A;margin:4px 0 0">Método: {metodo_label}</p>
                </td></tr>
              </table>

              <!-- Productos -->
              <p style="font-size:12px;font-weight:500;letter-spacing:2px;color:#B0BEB8;text-transform:uppercase;margin:0 0 12px">Detalle del pedido</p>
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:16px">
                <tr>
                  <th style="font-size:11px;color:#B0BEB8;font-weight:500;text-align:left;padding-bottom:8px;border-bottom:2px solid #E8E8E4">Producto</th>
                  <th style="font-size:11px;color:#B0BEB8;font-weight:500;text-align:center;padding-bottom:8px;border-bottom:2px solid #E8E8E4">Cant.</th>
                  <th style="font-size:11px;color:#B0BEB8;font-weight:500;text-align:right;padding-bottom:8px;border-bottom:2px solid #E8E8E4">Precio</th>
                </tr>
                {items_html}
                <tr>
                  <td colspan="2" style="padding:12px 0 0;font-size:14px;font-weight:600;color:#0F1A14">Total</td>
                  <td style="padding:12px 0 0;font-size:16px;font-weight:700;color:#1D7A4F;text-align:right">${total:.2f} USD</td>
                </tr>
              </table>

              <!-- CTA -->
              <table cellpadding="0" cellspacing="0" style="margin:28px 0">
                <tr><td style="background:#1D7A4F;border-radius:2px">
                  <a href="{FRONTEND_URL}/login.html" style="display:inline-block;padding:12px 28px;color:white;text-decoration:none;font-size:14px;font-weight:500">
                    Ver mi pedido →
                  </a>
                </td></tr>
              </table>

              <p style="font-size:12px;color:#B0BEB8;line-height:1.6;margin:0">
                ¿Tienes dudas? Escríbenos por WhatsApp al +57 310 888 7296 o visita <a href="{FRONTEND_URL}/contacto.html" style="color:#1D7A4F">velonox.co/contacto</a>
              </p>
            </td></tr>

            <!-- Footer -->
            <tr><td style="background:#0F1A14;padding:24px 40px;text-align:center">
              <p style="font-size:11px;color:#4A6A5A;margin:0">© 2026 Velonox · Cocina de por vida.</p>
            </td></tr>

          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """
    return send_email(to, f"Tu pedido Velonox #{order_id[:8].upper()} fue confirmado", html)


def email_recuperacion_password(to: str, nombre: str, reset_link: str):
    """Email con el link para restablecer la contraseña."""
    html = f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#F5F5F3;padding:40px 0;font-family:'DM Sans',Arial,sans-serif;">
      <tr><td align="center">
        <table width="480" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;overflow:hidden;">
          <tr><td style="background:#0F1A14;padding:28px 32px;">
            <span style="font-family:Georgia,serif;font-size:24px;font-weight:700;">
              <span style="color:#C8D8C0;">Velo</span><span style="color:#1D7A4F;">nox</span>
            </span>
          </td></tr>
          <tr><td style="padding:32px;">
            <p style="font-size:15px;color:#0F1A14;margin-bottom:16px;">Hola {nombre},</p>
            <p style="font-size:14px;color:#555;line-height:1.6;margin-bottom:24px;">
              Recibimos una solicitud para restablecer tu contraseña. Si fuiste tú, haz clic en el botón de abajo.
              Este link es válido por 30 minutos.
            </p>
            <table cellpadding="0" cellspacing="0"><tr><td style="border-radius:2px;background:#1D7A4F;">
              <a href="{reset_link}" style="display:inline-block;padding:14px 28px;color:#ffffff;text-decoration:none;font-size:14px;font-weight:600;">
                Restablecer contraseña
              </a>
            </td></tr></table>
            <p style="font-size:12.5px;color:#999;margin-top:24px;">
              Si no solicitaste esto, puedes ignorar este correo — tu contraseña seguirá siendo la misma.
            </p>
          </td></tr>
          <tr><td style="background:#0F1A14;padding:20px 32px;text-align:center;">
            <p style="font-size:11px;color:#4A6A5A;">© 2026 Velonox</p>
          </td></tr>
        </table>
      </td></tr>
    </table>
    """
    return send_email(to, "Restablece tu contraseña — Velonox", html)