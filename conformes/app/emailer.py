"""
Envío del conforme por correo, con dos transportes intercambiables.

- **Resend (HTTPS)**: el de producción. El plan gratuito de Render bloquea los
  puertos de SMTP, así que el puerto 443 es el único camino que queda. Además
  el remitente va en el dominio del cliente, con SPF y DKIM de Resend, que
  entrega mucho mejor que una cuenta Gmail gratuita.
- **Gmail SMTP**: el de desarrollo local, donde no hay bloqueo ni hace falta
  una clave de Resend para probar.

Lo elige `config.usa_resend()` según haya o no clave. El mensaje se arma una
sola vez y cada transporte lo entrega a su manera.

Ningún secreto vive aquí: todo llega por variables de entorno.
"""
import base64
import json
import logging
import re
import smtplib
import urllib.error
import urllib.request
from email.message import EmailMessage

from . import config
from .models import decodificar_foto

log = logging.getLogger("acta")

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465  # SSL

RESEND_URL = "https://api.resend.com/emails"
RESEND_TIMEOUT = 30


def _linea_fotos(acta) -> str:
    """Línea del cuerpo que anuncia las fotos; vacía si el acta no trae."""
    total = sum(len(u.fotos) for u in acta.unidades)
    return f"Fotografías adjuntas: {total}\n" if total else ""


def _nombre_foto(indice_unidad: int, identificador: str, n: int) -> str:
    """
    Nombre de archivo que se entiende sin abrirlo.

    Quien reciba el correo verá 'unidad-01-9BWZZZ377VT004251-foto-2.jpg' y
    sabrá de qué vehículo habla sin tener que abrir las doce fotos.
    """
    limpio = re.sub(r"[^A-Za-z0-9]", "", identificador)[:20] or "sin-id"
    return f"unidad-{indice_unidad:02d}-{limpio}-foto-{n}.jpg"


def _adjuntos(pdf_bytes: bytes, folio: str, acta):
    """Lista de (nombre, bytes) con el PDF y todas las fotos en tamaño completo."""
    salida = [(f"conforme_transferencia_{folio}.pdf", pdf_bytes)]
    # En el PDF solo van miniaturas, para que el documento siga siendo
    # liviano; el detalle del daño se ve en estos archivos.
    for i, unidad in enumerate(acta.unidades, start=1):
        for n, foto in enumerate(unidad.fotos, start=1):
            try:
                salida.append((_nombre_foto(i, unidad.identificador, n),
                               decodificar_foto(foto)))
            except Exception:
                log.warning("Foto %s de la unidad %s ilegible; no se adjunta", n, i)
    return salida


def _cuerpo(folio: str, acta) -> str:
    return (
        f"Adjuntamos el conforme de recepción/entrega para la transferencia "
        f"de responsabilidades.\n\n"
        f"Lugar: {acta.lugar}\n"
        f"Unidad movida en: {acta.transporte_legible()} de placa {acta.transporte_placa}\n"
        f"Folio: {folio}\n"
        f"Entrega: {acta.entrega.nombre} ({acta.entrega.tipo_documento} {acta.entrega.documento})\n"
        f"Recibe: {acta.recibe.nombre} ({acta.recibe.tipo_documento} {acta.recibe.documento})\n"
        f"Unidades: {len(acta.unidades)}\n"
        f"{_linea_fotos(acta)}"
        f"\n"
        f"Este es un mensaje automático. Documento generado electrónicamente."
    )


def enviar_acta(pdf_bytes: bytes, folio: str, acta, empresa: str) -> None:
    """
    Envía el conforme al gerente, a quien entrega y a quien recibe.

    Lanza excepción si el envío falla; el llamador la maneja y devuelve el PDF
    igual, para que el conforme nunca se pierda por un problema de correo.
    """
    destinatarios = _destinatarios_unicos([
        config.MANAGER_EMAIL,
        str(acta.entrega.email),
        str(acta.recibe.email),
    ])
    asunto = f"Conforme de entrega - Folio {folio}"
    remitente = f"Conformes {empresa} <{config.remitente()}>"
    cuerpo = _cuerpo(folio, acta)
    adjuntos = _adjuntos(pdf_bytes, folio, acta)

    if config.usa_resend():
        _enviar_por_resend(remitente, destinatarios, asunto, cuerpo, adjuntos)
    else:
        _enviar_por_smtp(remitente, destinatarios, asunto, cuerpo, adjuntos)


def _enviar_por_resend(remitente, destinatarios, asunto, cuerpo, adjuntos):
    """
    Entrega por la API HTTPS de Resend.

    Se usa urllib en vez de una librería: es una sola petición y no justifica
    sumarle una dependencia al proyecto.
    """
    payload = {
        "from": remitente,
        "to": destinatarios,
        "subject": asunto,
        "text": cuerpo,
        "attachments": [
            {"filename": nombre, "content": base64.b64encode(datos).decode()}
            for nombre, datos in adjuntos
        ],
    }
    if config.MANAGER_EMAIL:
        payload["reply_to"] = config.MANAGER_EMAIL   # las respuestas al gerente

    req = urllib.request.Request(
        RESEND_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {config.RESEND_API_KEY}",
            "Content-Type": "application/json",
            # Resend está detrás de Cloudflare, que bloquea el User-Agent por
            # defecto de urllib ("Python-urllib/3.x") con un 403 "error code:
            # 1010" antes de que la petición llegue a Resend. Cualquier nombre
            # propio basta.
            "User-Agent": "conformes-rexcarga/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=RESEND_TIMEOUT) as r:
            respuesta = json.loads(r.read() or b"{}")
        log.info("Conforme enviado por Resend (id %s)", respuesta.get("id"))
    except urllib.error.HTTPError as e:
        # El detalle de Resend explica el motivo real (dominio sin verificar,
        # remitente no autorizado, adjuntos demasiado grandes). Sin esto, el
        # log solo diría "HTTP 403" y no habría por dónde empezar.
        detalle = e.read().decode(errors="replace")[:500]
        raise RuntimeError(f"Resend rechazó el envío ({e.code}): {detalle}") from e


def _enviar_por_smtp(remitente, destinatarios, asunto, cuerpo, adjuntos):
    """Entrega por Gmail SMTP. Solo sirve en local: Render free lo bloquea."""
    msg = EmailMessage()
    msg["Subject"] = asunto
    msg["From"] = remitente
    msg["To"] = ", ".join(destinatarios)
    if config.MANAGER_EMAIL:
        msg["Reply-To"] = config.MANAGER_EMAIL
    msg.set_content(cuerpo)
    for nombre, datos in adjuntos:
        if nombre.lower().endswith(".pdf"):
            msg.add_attachment(datos, maintype="application", subtype="pdf",
                               filename=nombre)
        else:
            msg.add_attachment(datos, maintype="image", subtype="jpeg",
                               filename=nombre)

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
