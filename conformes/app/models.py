"""
Modelo de datos del acta y validación.

Este módulo es el "contrato" entre el formulario y el backend. Toda la
validación importante ocurre aquí, en el servidor, donde no se puede saltar
desde el navegador.
"""
import base64
import binascii
from io import BytesIO
from typing import List, Literal

from PIL import Image
from pydantic import BaseModel, EmailStr, Field, field_validator

TipoDocumento = Literal["CC", "CE", "PAS", "NIT"]
TipoIdentificador = Literal["vin", "placa"]

# Con qué se mueven las unidades. Los valores viajan en ASCII para no depender
# de la "ñ" en el payload; la etiqueta bonita se resuelve al pintar el PDF.
TipoTransporte = Literal["ninera", "grua", "rodado"]
ETIQUETA_TRANSPORTE = {
    "ninera": "Niñera",
    "grua": "Grúa",
    "rodado": "Rodado",
}

# Para quién se hace el transporte. El nombre y el logo de cada uno viven en
# config.CLIENTES: aquí solo se valida que la clave exista.
Cliente = Literal["rexcarga", "hal"]

# Placa del vehículo que hace el movimiento: 6 caracteres alfanuméricos.
_MAX_PLACA = 6

# Mínimo de píxeles con tinta para considerar que una firma no está en blanco.
_MIN_PIXELES_FIRMA = 40

# --- Fotos de las unidades ---
# El navegador reduce las fotos antes de subirlas (ver app.js): llegan como
# JPEG de ~1280 px y unos 260 KB. Estos topes NO son límites de producto sino
# válvulas de seguridad: sin ellos, cualquiera puede mandarle al servidor lo
# que quiera. Una niñera carga 9 unidades como máximo, así que el uso real
# queda muy por debajo.
_MAX_FOTOS_POR_UNIDAD = 15
_MAX_BYTES_FOTO = 2 * 1024 * 1024        # 2 MB por foto ya reducida
_MAX_BYTES_FOTOS_TOTAL = 20 * 1024 * 1024  # 20 MB sumando todas las unidades
_FORMATOS_FOTO = {"JPEG", "PNG", "WEBP"}


def _texto_obligatorio(v: str) -> str:
    v = (v or "").strip()
    if not v:
        raise ValueError("Este campo es obligatorio")
    return v


def decodificar_firma(data_url: str) -> Image.Image:
    """
    Recibe un data URL 'data:image/png;base64,...', lo decodifica a imagen y
    verifica que NO esté en blanco (canvas sin trazos). Devuelve la imagen
    PIL lista para incrustar en el PDF, o lanza ValueError si es inválida.
    """
    if not data_url or "," not in data_url:
        raise ValueError("Firma inválida o vacía")

    _, b64 = data_url.split(",", 1)
    try:
        crudo = base64.b64decode(b64)
    except (binascii.Error, ValueError):
        raise ValueError("Firma con formato inválido")

    try:
        img = Image.open(BytesIO(crudo))
        img.load()
    except Exception:
        raise ValueError("No se pudo leer la firma")

    # El canvas exporta PNG con fondo transparente y trazo oscuro.
    # Si el canal alfa no tiene suficientes píxeles visibles -> está en blanco.
    rgba = img.convert("RGBA")
    alfa = rgba.getchannel("A")
    visibles = sum(1 for p in alfa.getdata() if p > 10)
    if visibles < _MIN_PIXELES_FIRMA:
        raise ValueError("La firma está en blanco")

    return rgba


def decodificar_foto(data_url: str) -> bytes:
    """
    Valida una foto que llega del formulario y devuelve sus bytes.

    Comprueba que sea una imagen de verdad y no un archivo disfrazado: Pillow
    la abre y la verifica. No la re-codificamos porque el navegador ya la
    rehizo en un canvas al reducirla, y eso deja el JPEG limpio de metadatos
    (incluida la ubicación GPS que traen las fotos de celular).
    """
    if not data_url or "," not in data_url:
        raise ValueError("Foto inválida o vacía")

    cabecera, b64 = data_url.split(",", 1)
    if not cabecera.startswith("data:image/"):
        raise ValueError("La foto no es una imagen")

    try:
        crudo = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("Foto con formato inválido")

    if len(crudo) > _MAX_BYTES_FOTO:
        raise ValueError(f"Cada foto debe pesar menos de {_MAX_BYTES_FOTO // (1024*1024)} MB")

    try:
        img = Image.open(BytesIO(crudo))
        formato = img.format
        img.verify()          # verify() invalida la imagen: hay que reabrirla para usarla
    except Exception:
        raise ValueError("No se pudo leer la foto")

    if formato not in _FORMATOS_FOTO:
        raise ValueError("Formato de foto no admitido")

    return crudo


class Parte(BaseModel):
    """Quien entrega o quien recibe las unidades."""
    nombre: str
    tipo_documento: TipoDocumento = "CC"
    documento: str
    email: EmailStr
    firma: str  # data URL PNG en base64

    _v_nombre = field_validator("nombre")(classmethod(lambda cls, v: _texto_obligatorio(v)))
    _v_documento = field_validator("documento")(classmethod(lambda cls, v: _texto_obligatorio(v)))

    @field_validator("firma")
    @classmethod
    def _validar_firma(cls, v: str) -> str:
        # Verifica que decodifique y no esté en blanco; conserva el data URL.
        decodificar_firma(v)
        return v


class Unidad(BaseModel):
    """Una unidad (vehículo) transferida, con su identificador y observación."""
    identificador_tipo: TipoIdentificador
    identificador: str
    observacion: str
    fotos: List[str] = Field(default_factory=list)   # data URLs; opcionales

    _v_id = field_validator("identificador")(classmethod(lambda cls, v: _texto_obligatorio(v)))
    _v_obs = field_validator("observacion")(classmethod(lambda cls, v: _texto_obligatorio(v)))

    @field_validator("identificador")
    @classmethod
    def _normalizar_id(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("fotos")
    @classmethod
    def _validar_fotos(cls, v: List[str]) -> List[str]:
        if len(v) > _MAX_FOTOS_POR_UNIDAD:
            raise ValueError(f"Máximo {_MAX_FOTOS_POR_UNIDAD} fotos por unidad")
        for foto in v:
            decodificar_foto(foto)     # lanza ValueError si algo no cuadra
        return v


class ActaRequest(BaseModel):
    """Payload completo que llega desde el formulario."""
    cliente: Cliente
    lugar: str
    transporte_tipo: TipoTransporte
    transporte_placa: str
    entrega: Parte
    recibe: Parte
    unidades: List[Unidad] = Field(min_length=1)

    _v_lugar = field_validator("lugar")(classmethod(lambda cls, v: _texto_obligatorio(v)))

    @field_validator("transporte_placa")
    @classmethod
    def _validar_placa_transporte(cls, v: str) -> str:
        """
        Normaliza y valida la placa de la niñera / grúa / vehículo rodado.

        Se aceptan las formas en que la gente la escribe ('abc-123', 'ABC 123')
        y se guarda canónica en mayúsculas y sin separadores.
        """
        v = (v or "").strip().upper().replace("-", "").replace(" ", "")
        if not v:
            raise ValueError("La placa del vehículo de transporte es obligatoria")
        if not (v.isascii() and v.isalnum()):
            raise ValueError("La placa solo admite letras y números")
        if len(v) > _MAX_PLACA:
            raise ValueError(f"La placa no puede tener más de {_MAX_PLACA} caracteres")
        return v

    @field_validator("unidades")
    @classmethod
    def _validar_peso_total(cls, v: List[Unidad]) -> List[Unidad]:
        """
        Vigila el peso sumado de todas las fotos del acta.

        El tope por unidad no alcanza: nueve unidades en su límite darían un
        correo que ningún buzón acepta. Este control ve el total, que es lo
        que de verdad viaja.
        """
        total = sum(len(decodificar_foto(f)) for u in v for f in u.fotos)
        if total > _MAX_BYTES_FOTOS_TOTAL:
            raise ValueError(
                f"Las fotos suman {total // (1024*1024)} MB y el máximo es "
                f"{_MAX_BYTES_FOTOS_TOTAL // (1024*1024)} MB"
            )
        return v

    def transporte_legible(self) -> str:
        """Etiqueta del tipo de transporte para mostrar al humano."""
        return ETIQUETA_TRANSPORTE[self.transporte_tipo]
