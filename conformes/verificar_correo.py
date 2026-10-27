"""
Verifica la configuración de correo sin tener que llenar el formulario.

  python verificar_correo.py            -> solo revisa variables y login SMTP
  python verificar_correo.py --enviar   -> además manda un acta de prueba real

Se ejecuta desde la raíz del proyecto y lee el .env por su cuenta.
"""
import base64
import io
import os
import smtplib
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
if not (RAIZ / "app").is_dir():
    RAIZ = Path.cwd()
sys.path.insert(0, str(RAIZ))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(RAIZ / ".env")

from app import config  # noqa: E402  (después de cargar el .env)

OK, MAL, AVISO = "  OK  ", " FALLA", " AVISO"


def revisar_variables():
    """Revisa que estén las variables y avisa de los errores típicos."""
    print("\n1) Variables de entorno")
    problemas = []

    faltan = config.missing_email_config()
    for nombre in ("GMAIL_USER", "GMAIL_APP_PASSWORD", "MANAGER_EMAIL"):
        if nombre in faltan:
            print(f"[{MAL}] {nombre} está vacía")
            problemas.append(nombre)
        elif nombre == "GMAIL_APP_PASSWORD":
            print(f"[{OK}] {nombre} presente ({len(config.GMAIL_APP_PASSWORD)} caracteres)")
        else:
            print(f"[{OK}] {nombre} = {getattr(config, nombre)}")

    # config normaliza la clave, así que para avisar de los espacios hay que
    # mirar el valor crudo tal como quedó en el .env o en el panel de Render.
    crudo = os.getenv("GMAIL_APP_PASSWORD", "")
    clave = config.GMAIL_APP_PASSWORD
    if clave:
        if " " in crudo:
            print(f"[{AVISO}] La contraseña venía con espacios "
                  f"({len(crudo)} caracteres); config.py los quitó automáticamente.")
        if len(clave) != 16:
            print(f"[{AVISO}] La app password suele tener 16 caracteres, esta tiene {len(clave)}. "
                  "Si el login falla, revisa que no se haya copiado incompleta.")

    if config.GMAIL_USER and config.GMAIL_USER == config.MANAGER_EMAIL:
        print(f"[{AVISO}] MANAGER_EMAIL es la misma cuenta que envía. "
              "Las respuestas caerían en el buzón automático que nadie lee.")

    print(f"[{OK}] COMPANY_NAME = {config.COMPANY_NAME}")
    print(f"[{OK}] Logo = {config.logo_file() or 'sin logo (el PDF lo omite)'}")
    return problemas


def probar_login():
    """Se conecta a Gmail y hace login, sin enviar nada."""
    print("\n2) Login SMTP en smtp.gmail.com:465")
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as smtp:
            smtp.login(config.GMAIL_USER, config.GMAIL_APP_PASSWORD)
        print(f"[{OK}] Login correcto. Las credenciales sirven.")
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"[{MAL}] Gmail rechazó las credenciales: {e.smtp_code} {e.smtp_error}")
        print("       Causas típicas:")
        print("       - La contraseña de aplicación se copió con espacios.")
        print("       - Se usó la contraseña normal de la cuenta, no la de aplicación.")
        print("       - La verificación en dos pasos no quedó activa.")
        return False
    except Exception as e:
        print(f"[{MAL}] No se pudo conectar: {type(e).__name__}: {e}")
        return False


def _firma_de_prueba():
    """Un garabato con tinta suficiente para pasar decodificar_firma()."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (400, 150), (255, 255, 255, 0))
    d = ImageDraw.Draw(img)
    d.line([(20, 120), (120, 30), (200, 110), (300, 40), (380, 100)],
           fill=(0, 0, 0, 255), width=5)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def enviar_prueba():
    """Recorre la cadena completa: modelo -> PDF -> correo real."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from app.models import ActaRequest
    from app.pdf_generator import generar_pdf
    from app.emailer import enviar_acta

    print("\n3) Envío de un acta de prueba")
    firma = _firma_de_prueba()
    destino = config.MANAGER_EMAIL
    acta = ActaRequest(
        lugar="PRUEBA DE CONFIGURACION — ignorar este correo",
        entrega={"nombre": "Prueba Entrega", "tipo_documento": "CC",
                 "documento": "0000000000", "email": destino, "firma": firma},
        recibe={"nombre": "Prueba Recibe", "tipo_documento": "CC",
                "documento": "0000000001", "email": destino, "firma": firma},
        unidades=[{"identificador_tipo": "vin", "identificador": "PRUEBA0000000000",
                   "observacion": "Acta de prueba generada para validar el correo."}],
    )
    fecha = datetime.now(ZoneInfo(config.TIMEZONE))
    folio = "TR-PRUEBA-0000"
    pdf = generar_pdf(acta, folio, fecha, logo_path=config.logo_file(),
                      empresa=config.COMPANY_NAME)
    print(f"[{OK}] PDF generado ({len(pdf)} bytes)")
    enviar_acta(pdf, folio, acta, config.COMPANY_NAME)
    print(f"[{OK}] Correo enviado a: {destino}")
    print("       Revisa la bandeja (y la carpeta de spam la primera vez).")


def main():
    print("=" * 60)
    print("Verificación de la configuración de correo")
    print("=" * 60)

    problemas = revisar_variables()
    if problemas:
        print("\nCorrige lo marcado como FALLA en el .env y vuelve a correr.")
        return 1

    if not probar_login():
        return 1

    if "--enviar" in sys.argv:
        try:
            enviar_prueba()
        except Exception as e:
            print(f"[{MAL}] Falló el envío: {type(e).__name__}: {e}")
            return 1
    else:
        print("\nCredenciales validadas. Para mandar un acta de prueba real:")
        print("   .venv/bin/python verificar_correo.py --enviar")

    print("\nListo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
