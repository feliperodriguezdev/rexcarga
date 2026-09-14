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

# Placa del vehículo que hace el movimiento: 6 caracteres alfanuméricos.
_MAX_PLACA = 6

# Mínimo de píxeles con tinta para considerar que una firma no está en blanco.
_MIN_PIXELES_FIRMA = 40


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

    _v_id = field_validator("identificador")(classmethod(lambda cls, v: _texto_obligatorio(v)))
    _v_obs = field_validator("observacion")(classmethod(lambda cls, v: _texto_obligatorio(v)))

    @field_validator("identificador")
    @classmethod
    def _normalizar_id(cls, v: str) -> str:
        return v.strip().upper()


class ActaRequest(BaseModel):
    """Payload completo que llega desde el formulario."""
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

    def transporte_legible(self) -> str:
        """Etiqueta del tipo de transporte para mostrar al humano."""
        return ETIQUETA_TRANSPORTE[self.transporte_tipo]
