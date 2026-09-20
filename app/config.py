"""
Configuración de la aplicación por variables de entorno.

Todo lo sensible (contraseña de aplicación de Gmail) y todo lo específico
del cliente (correo del gerente, nombre de la empresa, logo) vive aquí y se
lee del entorno. Nada de esto se manda desde el navegador.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Carga el .env del proyecto si existe, para que `uvicorn app.main:app`
# funcione sin acordarse del `set -a; source .env` (olvidarlo ya costó dos
# depuraciones: la app arranca "bien" pero sin poder enviar correo).
# En Render no hay archivo y las variables llegan del panel, así que esto no
# hace nada allá. No pisa lo que ya esté en el entorno: el sistema manda sobre
# el archivo, que es lo que permite sobrescribir variables en las pruebas.
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR.parent / ".env")
except ImportError:      # el proyecto sigue funcionando sin la librería
    pass


def _var(nombre: str, defecto: str = "") -> str:
    """Lee una variable de entorno sin espacios sobrantes a los lados."""
    return os.getenv(nombre, defecto).strip()


def _clave_app(nombre: str) -> str:
    """
    Lee la contraseña de aplicación de Gmail quitándole TODOS los espacios.

    Google la muestra en grupos de cuatro ('abcd efgh ijkl mnop') y así es como
    termina pegada en el .env o en el panel de Render. Gmail la rechaza con un
    535 genérico que no menciona los espacios, así que el error se diagnostica
    muy mal justo donde no hay consola a la mano. Normalizarla aquí es más
    barato que depurarlo en producción.
    """
    return os.getenv(nombre, "").replace(" ", "").strip()


# --- Envío de correo (Gmail SMTP) ---
GMAIL_USER = _var("GMAIL_USER")                     # ej: actas.transportexyz@gmail.com
GMAIL_APP_PASSWORD = _clave_app("GMAIL_APP_PASSWORD")  # app password de 16 caracteres

# --- Datos del cliente (hardcodeados por entorno para este MVP) ---
MANAGER_EMAIL = _var("MANAGER_EMAIL")               # correo fijo del gerente
COMPANY_NAME = _var("COMPANY_NAME", "Empresa de Transporte")

# Ruta a un PNG con el logo del cliente (opcional). Si no existe, se omite.
LOGO_PATH = _var("LOGO_PATH", str(BASE_DIR / "static" / "logo.png"))

# Zona horaria para la fecha/hora del acta (Colombia)
TIMEZONE = _var("TIMEZONE", "America/Bogota")


def logo_file():
    """Devuelve la ruta del logo si el archivo existe, si no None."""
    p = Path(LOGO_PATH)
    return str(p) if p.is_file() else None


def missing_email_config():
    """Lista de variables de correo que faltan, para avisar en el arranque."""
    faltan = []
    if not GMAIL_USER:
        faltan.append("GMAIL_USER")
    if not GMAIL_APP_PASSWORD:
        faltan.append("GMAIL_APP_PASSWORD")
    if not MANAGER_EMAIL:
        faltan.append("MANAGER_EMAIL")
    return faltan
