"""
Generación del PDF del acta.

Regla clave: UNA HOJA POR UNIDAD. Cada hoja es un acta completa y autónoma
para esa unidad, con los datos de quien entrega / recibe arriba y las dos
firmas abajo. Las firmas se capturan una sola vez y se reutilizan en todas
las hojas.
"""
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

from .models import ActaRequest, Parte, decodificar_firma

# Paleta (coherente con el frontend)
INK = (0.086, 0.125, 0.169)     # #16202B
SLATE = (0.357, 0.408, 0.459)   # #5B6875
LINE = (0.839, 0.863, 0.886)    # #D6DCE2

PAGE_W, PAGE_H = letter
MARGIN = 18 * mm

_estilo_obs = ParagraphStyle(
    "obs", fontName="Helvetica", fontSize=10.5, leading=15,
    textColor=INK, alignment=TA_LEFT,
)


def _firma_a_reader(data_url: str) -> ImageReader:
    """Convierte el data URL de la firma en algo que ReportLab pueda dibujar."""
    img = decodificar_firma(data_url)  # PIL RGBA, ya validada
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def _dibujar_hoja(c, acta: ActaRequest, unidad, indice: int, total: int,
                  folio: str, fecha_txt: str, logo_reader,
                  firma_entrega, firma_recibe, empresa: str):
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
    y -= 34 * mm
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
    tope_firmas = MARGIN + 42 * mm
    alto_disp = y - tope_firmas
    p = Paragraph(unidad.observacion.replace("\n", "<br/>"), _estilo_obs)
    _, alto_real = p.wrap(ancho_util, alto_disp)
    p.drawOn(c, MARGIN, y - min(alto_real, alto_disp))

    # --- Firmas (abajo) ---
    yf = MARGIN + 34 * mm
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
        _dibujar_hoja(c, acta, unidad, i, total, folio, fecha_txt,
                      logo_reader, firma_entrega, firma_recibe, empresa)
        c.showPage()

    c.save()
    buf.seek(0)
    return buf.read()
