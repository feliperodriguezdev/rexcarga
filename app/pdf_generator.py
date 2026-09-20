"""
Generación del PDF del acta.

Regla clave: UNA HOJA POR UNIDAD. Cada hoja es un acta completa y autónoma
para esa unidad, con los datos de quien entrega / recibe arriba y las dos
firmas abajo. Las firmas se capturan una sola vez y se reutilizan en todas
las hojas.
"""
import logging
from datetime import datetime
from io import BytesIO

from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.utils import ImageReader

from .models import ActaRequest, Parte, decodificar_firma, decodificar_foto

log = logging.getLogger("acta")

# Paleta (coherente con el frontend)
INK = (0.086, 0.125, 0.169)     # #16202B
SLATE = (0.357, 0.408, 0.459)   # #5B6875
LINE = (0.839, 0.863, 0.886)    # #D6DCE2

PAGE_W, PAGE_H = letter
MARGIN = 18 * mm

# --- Geometría vertical de la hoja ---
# Estas medidas están ligadas entre sí y antes vivían como números sueltos
# repartidos por el código, lo que ya provocó un solape entre la observación
# y las firmas. Aquí el suelo del contenido se DEDUCE de dónde se apoyan las
# firmas y de cuánto miden, en vez de escribirse a mano.
_ALTO_BLOQUE_PARTE = 16 * mm      # del ancla a la línea del correo
_AIRE_TRAS_PARTES = 6 * mm        # respiro antes de la línea de la unidad
_BASE_FIRMAS = MARGIN + 12 * mm   # las firmas se apoyan casi sobre el pie
_ALTO_BLOQUE_FIRMA = 26 * mm      # la imagen (20 mm) arranca 6 mm sobre la base
_TOPE_CONTENIDO = _BASE_FIRMAS + _ALTO_BLOQUE_FIRMA + 2 * mm

_estilo_obs = ParagraphStyle(
    "obs", fontName="Helvetica", fontSize=10.5, leading=15,
    textColor=INK, alignment=TA_LEFT,
)


def _foto_a_miniatura(data_url: str, lado: int = 600) -> ImageReader:
    """
    Reduce una foto al tamaño en que se va a ver en la hoja.

    Incrustar la foto original multiplicaría por diez el peso del PDF, que
    viaja por correo. A 600 px una miniatura de 42 mm se imprime nítida.
    """
    crudo = decodificar_foto(data_url)
    img = Image.open(BytesIO(crudo))
    img = img.convert("RGB")
    img.thumbnail((lado, lado), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=75, optimize=True)
    buf.seek(0)
    return ImageReader(buf)


def _firma_a_reader(data_url: str) -> ImageReader:
    """Convierte el data URL de la firma en algo que ReportLab pueda dibujar."""
    img = decodificar_firma(data_url)  # PIL RGBA, ya validada
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


# --- Fotos de la unidad ---
# Van en la MISMA hoja, en una tira bajo las observaciones: cada hoja debe
# seguir siendo un acta autónoma. Las fotos en tamaño grande viajan como
# adjuntos del correo; aquí solo se necesita reconocer de qué daño se habla.
_FOTOS_POR_FILA = 4
_MAX_FILAS_FOTOS = 2                     # 8 miniaturas; el resto va solo adjunto
_HUECO_MINIATURA = 3 * mm

# La hoja tiene un presupuesto vertical fijo y la observación también lo
# necesita. Con las 4 fotos del caso típico caben grandes en una fila; si hay
# más, se encogen para que dos filas no se coman el texto.
_ALTO_MINIATURA_1_FILA = 30 * mm
_ALTO_MINIATURA_2_FILAS = 22 * mm


def _filas_y_alto(n_fotos: int):
    """Cuántas filas de miniaturas y de qué alto, según cuántas fotos haya."""
    if n_fotos <= _FOTOS_POR_FILA:
        return 1, _ALTO_MINIATURA_1_FILA
    return 2, _ALTO_MINIATURA_2_FILAS


def _alto_banda_fotos(unidad) -> float:
    """Espacio vertical que hay que reservarle a las fotos (0 si no hay)."""
    if not unidad.fotos:
        return 0.0
    filas, alto = _filas_y_alto(len(unidad.fotos))
    return 9 * mm + filas * alto + (filas - 1) * _HUECO_MINIATURA


def _dibujar_fotos(c, unidad, y_arriba: float, ancho_util: float, lectores):
    """
    Pinta las miniaturas empezando en y_arriba y bajando.

    Cada foto se encaja en su recuadro respetando la proporción: las verticales
    y las horizontales conviven en la misma tira sin deformarse.
    """
    if not lectores:
        return

    c.setFont("Helvetica-Bold", 9)
    c.setFillColorRGB(*SLATE)
    visibles = min(len(lectores), _FOTOS_POR_FILA * _MAX_FILAS_FOTOS)
    sobrantes = len(lectores) - visibles
    rotulo = f"FOTOS ({len(lectores)})"
    if sobrantes:
        rotulo += f" · las {sobrantes} restantes van adjuntas al correo"
    c.drawString(MARGIN, y_arriba, rotulo)

    _, alto_mini = _filas_y_alto(len(lectores))
    ancho_caja = (ancho_util - (_FOTOS_POR_FILA - 1) * _HUECO_MINIATURA) / _FOTOS_POR_FILA
    y = y_arriba - 4 * mm - alto_mini

    for i, lector in enumerate(lectores[:visibles]):
        fila, col = divmod(i, _FOTOS_POR_FILA)
        x = MARGIN + col * (ancho_caja + _HUECO_MINIATURA)
        y_caja = y - fila * (alto_mini + _HUECO_MINIATURA)

        c.setStrokeColorRGB(*LINE)
        c.setLineWidth(0.5)
        c.rect(x, y_caja, ancho_caja, alto_mini, stroke=1, fill=0)
        try:
            c.drawImage(lector, x + 0.5, y_caja + 0.5,
                        width=ancho_caja - 1, height=alto_mini - 1,
                        preserveAspectRatio=True, anchor="c")
        except Exception:
            pass      # una foto ilegible no puede tumbar el acta entera


def _dibujar_hoja(c, acta: ActaRequest, unidad, indice: int, total: int,
                  folio: str, fecha_txt: str, logo_reader,
                  firma_entrega, firma_recibe, empresa: str, fotos_unidad):
    ancho_util = PAGE_W - 2 * MARGIN
    y = PAGE_H - MARGIN

    # --- Encabezado ---
    if logo_reader is not None:
        try:
            c.drawImage(logo_reader, MARGIN, y - 14 * mm, height=14 * mm,
                        width=30 * mm, preserveAspectRatio=True, anchor="sw", mask="auto")
        except Exception:
            pass

    c.setFillColorRGB(*INK)
    c.setFont("Helvetica-Bold", 13)
    c.drawRightString(PAGE_W - MARGIN, y - 4 * mm, "CONFORME DE TRANSFERENCIA")
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(PAGE_W - MARGIN, y - 9 * mm, "DE RESPONSABILIDAD")
    c.setFillColorRGB(*SLATE)
    c.setFont("Helvetica", 8.5)
    c.drawRightString(PAGE_W - MARGIN, y - 14 * mm, empresa)

    y -= 20 * mm
    c.setStrokeColorRGB(*LINE)
    c.setLineWidth(1)
    c.line(MARGIN, y, PAGE_W - MARGIN, y)

    # Franja de metadatos: folio, unidad X de N, fecha, lugar y transporte
    y -= 6 * mm
    c.setFont("Helvetica-Bold", 9)
    c.setFillColorRGB(*INK)
    c.drawString(MARGIN, y, f"Folio: {folio}")
    c.drawRightString(PAGE_W - MARGIN, y, f"Unidad {indice} de {total}")
    y -= 5 * mm
    c.setFont("Helvetica", 9)
    c.setFillColorRGB(*SLATE)
    c.drawString(MARGIN, y, f"Fecha y hora: {fecha_txt}")
    y -= 5 * mm
    c.drawString(MARGIN, y, f"Lugar de la transferencia: {acta.lugar}")

    # Vehículo que hace el movimiento. La placa va en monoespaciada igual que
    # el identificador de la unidad: son códigos donde importa distinguir 0/O.
    y -= 5 * mm
    prefijo = f"Transporte: {acta.transporte_legible()} · Placa "
    c.drawString(MARGIN, y, prefijo)
    c.setFont("Courier-Bold", 9.5)
    c.setFillColorRGB(*INK)
    c.drawString(MARGIN + c.stringWidth(prefijo, "Helvetica", 9), y, acta.transporte_placa)
    c.setFont("Helvetica", 9)
    c.setFillColorRGB(*SLATE)

    # --- Partes (arriba) ---
    y -= 9 * mm
    col_w = ancho_util / 2
    _bloque_parte(c, "ENTREGA", acta.entrega, MARGIN, y, col_w - 4 * mm)
    _bloque_parte(c, "RECIBE", acta.recibe, MARGIN + col_w, y, col_w - 4 * mm)

    # --- Unidad + observación ---
    y -= _ALTO_BLOQUE_PARTE + _AIRE_TRAS_PARTES
    c.setStrokeColorRGB(*LINE)
    c.line(MARGIN, y, PAGE_W - MARGIN, y)
    y -= 6 * mm
    etiqueta = "VIN" if unidad.identificador_tipo == "vin" else "Placa"
    c.setFont("Helvetica-Bold", 10)
    c.setFillColorRGB(*SLATE)
    c.drawString(MARGIN, y, "UNIDAD")
    c.setFont("Courier-Bold", 15)
    c.setFillColorRGB(*INK)
    c.drawString(MARGIN + 22 * mm, y - 0.5 * mm, f"{etiqueta}: {unidad.identificador}")

    y -= 8 * mm
    c.setFont("Helvetica-Bold", 9)
    c.setFillColorRGB(*SLATE)
    c.drawString(MARGIN, y, "OBSERVACIONES")
    y -= 5 * mm

    # Observación con ajuste de línea. Se le reserva el espacio hasta la zona
    # de firmas; si el texto es más largo, ReportLab lo recorta a esa altura.
    tope_firmas = _TOPE_CONTENIDO
    banda_fotos = _alto_banda_fotos(unidad)
    alto_disp = y - tope_firmas - banda_fotos
    p = Paragraph(unidad.observacion.replace("\n", "<br/>"), _estilo_obs)
    _, alto_real = p.wrap(ancho_util, alto_disp)
    if alto_real > alto_disp:
        # drawOn pinta el párrafo COMPLETO hacia arriba desde la base que se
        # le da: un texto que no cabe no se recorta, se monta sobre la
        # etiqueta y el título de la unidad. split() devuelve solo el trozo
        # que entra en la altura disponible.
        trozos = p.split(ancho_util, alto_disp)
        if trozos:
            p = trozos[0]
            _, alto_real = p.wrap(ancho_util, alto_disp)
        log.warning("Observación de la unidad %s recortada: no cabe en la hoja", indice)
    alto_obs = min(alto_real, alto_disp)
    p.drawOn(c, MARGIN, y - alto_obs)

    # --- Fotos ---
    # Van pegadas a la observación, no ancladas al fondo: con un texto corto
    # quedaría un hueco blanco enorme en mitad de la hoja. El tope impide que
    # una observación larga las empuje sobre las firmas.
    if banda_fotos:
        y_fotos = max(y - alto_obs - 7 * mm, tope_firmas + banda_fotos - 4 * mm)
        _dibujar_fotos(c, unidad, y_fotos, ancho_util, fotos_unidad)

    # --- Firmas (abajo) ---
    yf = _BASE_FIRMAS
    c.setStrokeColorRGB(*LINE)
    c.line(MARGIN, yf + 4 * mm, PAGE_W - MARGIN, yf + 4 * mm)
    _bloque_firma(c, "Entrega", acta.entrega, firma_entrega, MARGIN, yf, col_w - 6 * mm)
    _bloque_firma(c, "Recibe", acta.recibe, firma_recibe, MARGIN + col_w, yf, col_w - 6 * mm)

    # --- Pie ---
    c.setFont("Helvetica", 7.5)
    c.setFillColorRGB(*SLATE)
    c.drawString(MARGIN, MARGIN - 6 * mm,
                 f"Documento generado electrónicamente · Folio {folio}")
    c.drawRightString(PAGE_W - MARGIN, MARGIN - 6 * mm, f"Página {indice} de {total}")


def _bloque_parte(c, titulo: str, parte: Parte, x: float, y: float, w: float):
    c.setFont("Helvetica-Bold", 9)
    c.setFillColorRGB(*SLATE)
    c.drawString(x, y, titulo)
    c.setFillColorRGB(*INK)
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(x, y - 6 * mm, parte.nombre[:40])
    c.setFont("Helvetica", 9)
    c.setFillColorRGB(*SLATE)
    c.drawString(x, y - 11 * mm, f"{parte.tipo_documento}: {parte.documento}")
    c.drawString(x, y - 16 * mm, parte.email[:42])


def _bloque_firma(c, rol: str, parte: Parte, firma_reader, x: float, y: float, w: float):
    # Imagen de la firma sobre la línea
    if firma_reader is not None:
        try:
            c.drawImage(firma_reader, x, y + 6 * mm, width=w, height=20 * mm,
                        preserveAspectRatio=True, anchor="sw", mask="auto")
        except Exception:
            pass
    c.setStrokeColorRGB(*INK)
    c.setLineWidth(0.8)
    c.line(x, y + 5 * mm, x + w, y + 5 * mm)
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColorRGB(*INK)
    c.drawString(x, y, f"{rol} · {parte.nombre[:34]}")
    c.setFont("Helvetica", 8)
    c.setFillColorRGB(*SLATE)
    c.drawString(x, y - 4 * mm, f"{parte.tipo_documento}: {parte.documento}")


def generar_pdf(acta: ActaRequest, folio: str, fecha: datetime,
                logo_path: str | None, empresa: str) -> bytes:
    """Construye el PDF completo (una hoja por unidad) y devuelve los bytes."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setTitle(f"Conforme de transferencia {folio}")

    fecha_txt = fecha.strftime("%Y-%m-%d %H:%M")
    logo_reader = None
    if logo_path:
        try:
            logo_reader = ImageReader(logo_path)
        except Exception:
            logo_reader = None

    # Las firmas se decodifican una sola vez y se reutilizan en cada hoja.
    firma_entrega = _firma_a_reader(acta.entrega.firma)
    firma_recibe = _firma_a_reader(acta.recibe.firma)

    total = len(acta.unidades)
    for i, unidad in enumerate(acta.unidades, start=1):
        # Se reducen de a una: con nueve unidades cargadas de fotos, hacerlo
        # todo de golpe hincharía la memoria del servidor sin necesidad.
        miniaturas = []
        for foto in unidad.fotos:
            try:
                miniaturas.append(_foto_a_miniatura(foto))
            except Exception:
                log.warning("Foto ilegible en la unidad %s; se omite del PDF", i)
        _dibujar_hoja(c, acta, unidad, i, total, folio, fecha_txt,
                      logo_reader, firma_entrega, firma_recibe, empresa, miniaturas)
        c.showPage()

    c.save()
    buf.seek(0)
    return buf.read()
