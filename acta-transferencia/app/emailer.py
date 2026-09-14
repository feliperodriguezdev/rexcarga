"""
Envío del acta por correo usando Gmail SMTP.

El remitente y el servidor están alineados (cuenta Gmail dedicada enviando a
través de Google), que es la mejor entregabilidad posible sin dominio propio.
La contraseña de aplicación vive en variables de entorno, nunca en el cliente.
"""
import smtplib
from email.message import EmailMessage

from . import config

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465  # SSL


def enviar_acta(pdf_bytes: bytes, folio: str, acta, empresa: str) -> None:
    """
    Envía el PDF a: gerente (config), quien entrega y quien recibe.
    Lanza excepción si el envío falla (el llamador la maneja).
    """
    destinatarios = _destinatarios_unicos([
        config.MANAGER_EMAIL,
        str(acta.entrega.email),
        str(acta.recibe.email),
    ])

    msg = EmailMessage()
    msg["Subject"] = f"Conforme de entrega - Folio {folio}"
    msg["From"] = f"Actas de Transferencia — {empresa} <{config.GMAIL_USER}>"
    msg["To"] = ", ".join(destinatarios)
    # Las respuestas caen en el buzón del gerente.
    if config.MANAGER_EMAIL:
        msg["Reply-To"] = config.MANAGER_EMAIL

    cuerpo = (
        f"Adjuntamos el conforme de recepción/entrega para la transferencia "
        f"de responsabilidades.\n\n"
        f"Lugar: {acta.lugar}\n"
        f"Unidad movida en: {acta.transporte_legible()} de placa {acta.transporte_placa}\n"
        f"Folio: {folio}\n"
        f"Entrega: {acta.entrega.nombre} ({acta.entrega.tipo_documento} {acta.entrega.documento})\n"
        f"Recibe: {acta.recibe.nombre} ({acta.recibe.tipo_documento} {acta.recibe.documento})\n"
        f"Unidades: {len(acta.unidades)}\n\n"
        f"Este es un mensaje automático. Documento generado electrónicamente."
    )
    msg.set_content(cuerpo)
    msg.add_attachment(
        pdf_bytes, maintype="application", subtype="pdf",
        filename=f"conforme_transferencia_{folio}.pdf",
    )

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=20) as smtp:
        smtp.login(config.GMAIL_USER, config.GMAIL_APP_PASSWORD)
        smtp.send_message(msg)


def _destinatarios_unicos(correos):
    """Quita vacíos y duplicados conservando el orden."""
    vistos = set()
    out = []
    for c in correos:
        c = (c or "").strip().lower()
        if c and c not in vistos:
            vistos.add(c)
            out.append(c)
    return out
