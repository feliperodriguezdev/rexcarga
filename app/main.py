"""
Aplicación FastAPI.

- GET  /            -> sirve el formulario (móvil-primero)
- POST /api/acta    -> valida, genera el PDF, lo envía por correo y devuelve
                       el PDF en base64 para el botón "Descargar respaldo"
- GET  /health      -> para el ping que mantiene despierta la app en Render
"""
import base64
import logging
import secrets
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from . import config
from .models import ActaRequest
from .pdf_generator import generar_pdf
from .emailer import enviar_acta

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("acta")

app = FastAPI(title="Acta de Transferencia de Responsabilidad")
app.mount("/static", StaticFiles(directory=config.BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(config.BASE_DIR / "templates"))


@app.on_event("startup")
def aviso_config():
    faltan = config.missing_email_config()
    if faltan:
        log.warning("Faltan variables de correo: %s. El envío fallará hasta configurarlas.",
                    ", ".join(faltan))


def _generar_folio(fecha: datetime) -> str:
    aleatorio = secrets.token_hex(2).upper()  # 4 caracteres
    return f"TR-{fecha.strftime('%Y%m%d')}-{aleatorio}"


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/")
def formulario(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "empresa": config.COMPANY_NAME},
    )


@app.post("/api/acta")
async def crear_acta(request: Request):
    datos = await request.json()

    # 1) Validación (servidor)
    try:
        acta = ActaRequest.model_validate(datos)
    except ValidationError as e:
        detalles = [
            {"campo": ".".join(str(x) for x in err.get("loc", [])),
             "mensaje": str(err.get("msg", ""))}
            for err in e.errors(include_url=False, include_input=False)
        ]
        return JSONResponse(status_code=422, content={
            "ok": False,
            "error": "Revisa los datos del formulario.",
            "detalles": detalles,
        })

    # 2) Folio y fecha los pone el servidor (no se confía en la hora del celular)
    fecha = datetime.now(ZoneInfo(config.TIMEZONE))
    folio = _generar_folio(fecha)

    # 3) PDF
    try:
        pdf_bytes = generar_pdf(
            acta, folio, fecha,
            logo_path=config.logo_file(),
            empresa=config.COMPANY_NAME,
        )
    except Exception:
        log.exception("Error generando el PDF")
        return JSONResponse(status_code=500, content={
            "ok": False,
            "error": "No se pudo generar el documento. Intenta de nuevo.",
        })

    pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")

    # 4) Envío de correo. Si falla, igual devolvemos el PDF para descarga.
    email_ok = True
    email_error = None
    if config.missing_email_config():
        email_ok = False
        email_error = "El envío de correo no está configurado en el servidor."
    else:
        try:
            enviar_acta(pdf_bytes, folio, acta, config.COMPANY_NAME)
        except Exception as e:
            log.exception("Error enviando el correo")
            email_ok = False
            email_error = "No se pudo enviar el correo. Descarga el PDF como respaldo."

    return {
        "ok": True,
        "folio": folio,
        "email_ok": email_ok,
        "email_error": email_error,
        "pdf_base64": pdf_b64,
        "filename": f"conforme_transferencia_{folio}.pdf",
    }
