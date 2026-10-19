# Genera public/img a partir de las fotos originales del cliente: difumina
# placas, reduce y re-codifica a WebP. Guardarlas sin exif= las despoja de
# metadatos (incluida la ubicación GPS). Requiere Pillow.
#
# Uso: python scripts/optimizar_fotos.py "<carpeta Favoritas para la web>" <carpeta logo_mapa> public/img
# (las dos carpetas salen de Favoritas.zip y logo_mapa.zip, del Drive del cliente)
#
# Ojo: también regenera el logo y el favicon sin cuantizar; si no cambiaron,
# descarta esos cambios con git checkout.
import sys, os
from PIL import Image, ImageOps, ImageDraw, ImageFilter

# Placas a difuminar, en píxeles de la foto escalada a 1000 de ancho
# (x1, y1, x2, y2). Incluye la placa pintada en la puerta y la del bumper.
PLACAS = {
    'hero': [(540, 305, 590, 337), (920, 300, 960, 325), (685, 362, 715, 380)],
    'nosotros': [(633, 343, 688, 380), (862, 425, 890, 447), (168, 358, 196, 377)],
    'servicio-grua': [(225, 480, 285, 517), (105, 545, 135, 595)],
    'servicio-ninera': [(457, 365, 488, 392), (703, 450, 728, 472), (655, 405, 685, 425)],
    'galeria/01': [(703, 322, 765, 356), (875, 400, 902, 428)],
    'galeria/02': [(372, 357, 418, 382)],
    'galeria/03': [(594, 344, 616, 366), (720, 402, 748, 420), (395, 348, 420, 366), (790, 345, 820, 370)],
    'galeria/04': [(188, 320, 228, 336)],
    'galeria/05': [(615, 445, 655, 462), (808, 540, 830, 558)],
    'galeria/06': [(243, 388, 310, 425), (118, 452, 145, 482)],
    'galeria/07': [(578, 240, 612, 263), (440, 288, 472, 306), (95, 292, 140, 315)],
    'galeria/08': [(263, 395, 345, 445), (90, 490, 112, 540)],
    'galeria/09': [(548, 362, 597, 400), (720, 448, 750, 475)],
    'galeria/10': [(430, 345, 451, 361), (300, 387, 323, 400), (690, 368, 725, 378),
                   (967, 356, 1000, 365), (965, 385, 1000, 410), (150, 340, 180, 352)],
    'galeria/11': [(655, 334, 679, 346), (775, 330, 803, 339), (692, 345, 708, 365), (820, 355, 840, 368)],
    'galeria/12': [(574, 258, 614, 285), (766, 322, 800, 342)],
    'galeria/13': [(662, 345, 705, 368), (848, 422, 874, 442), (850, 350, 875, 368)],
    'galeria/14': [(540, 428, 582, 450), (758, 535, 790, 557)],
}


def difuminar_placas(im, cajas):
    escala = im.width / 1000
    for x1, y1, x2, y2 in cajas:
        mx, my = (x2 - x1) * .2, (y2 - y1) * .3  # margen: las cajas son a ojo
        caja = tuple(round(v * escala) for v in (x1 - mx, y1 - my, x2 + mx, y2 + my))
        trozo = im.crop(caja)
        # Pixelar y luego suavizar: ilegible y sin el aspecto de mosaico
        chico = trozo.resize((max(1, trozo.width // 12), max(1, trozo.height // 12)), Image.BILINEAR)
        trozo = chico.resize(trozo.size, Image.BILINEAR).filter(ImageFilter.GaussianBlur(trozo.height / 8))
        im.paste(trozo, caja[:2])
    return im

F, L, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
W = 'WhatsApp Image 2026-'


def guardar(src, dst, ancho, calidad=78):
    im = ImageOps.exif_transpose(Image.open(src)).convert('RGB')
    im = difuminar_placas(im, PLACAS.get(dst, []))
    if im.width > ancho:
        im = im.resize((ancho, round(im.height * ancho / im.width)), Image.LANCZOS)
    im.save(os.path.join(OUT, dst + '.webp'), quality=calidad, method=6)
    print(dst, im.size)


fav = lambda n: os.path.join(F, n)
guardar(fav(W + '10-15 at 9.48.30 AM.jpeg'), 'hero', 1920, 72)
guardar(fav(W + '07-02 at 7.31.55 AM.jpeg'), 'servicio-ninera', 1200)
guardar(fav(W + '10-15 at 12.06.27 PM.jpeg'), 'servicio-grua', 1200)
guardar(fav(W + '10-16 at 11.50.52 AM.jpeg'), 'nosotros', 1200)
guardar(os.path.join(L, 'Mapa logístico de Colombia con cobertura nacional.png'), 'mapa-cobertura', 900, 80)

galeria = ['- VAK 536.jpeg', '----.jpeg', W + '06-15 at 3.25.32 PM (1).jpeg', W + '06-22 at 5.09.55 PM.jpeg',
           W + '06-24 at 6.32.01 PM.jpeg', W + '07-04 at 3.33.56 PM.jpeg', W + '07-07 at 6.31.10 PM.jpeg',
           W + '10-15 at 12.06.27 PM (4).jpeg', W + '10-15 at 12.06.28 PM.jpeg', W + '10-15 at 9.48.43 AM.jpeg',
           W + '10-15 at 9.49.37 AM.jpeg', W + '10-16 at 11.50.30 AM.jpeg', W + '10-16 at 11.50.36 AM.jpeg',
           W + '10-16 at 11.51.13 AM.jpeg']
for i, n in enumerate(galeria, 1):
    guardar(fav(n), f'galeria/{i:02d}', 1200, 75)

# Logo: sello circular sobre fondo blanco opaco. Se recorta al círculo y lo de
# afuera queda transparente, para que funcione sobre cualquier fondo.
lg = Image.open(os.path.join(L, 'logo.png')).convert('RGBA')
gris = lg.convert('L')
caja = gris.point(lambda v: 255 if v < 235 else 0).getbbox()
lg = lg.crop(caja)
mascara = Image.new('L', lg.size, 0)
ImageDraw.Draw(mascara).ellipse((0, 0, lg.width - 1, lg.height - 1), fill=255)
lg.putalpha(mascara)
lg.save(os.path.join(OUT, 'logo.png'), optimize=True)
lg.resize((180, round(180 * lg.height / lg.width)), Image.LANCZOS).save(os.path.join(OUT, 'logo-180.png'), optimize=True)
ico = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
ico.paste(lg.resize((64, 64), Image.LANCZOS))
ico.save(os.path.join(OUT, '..', 'favicon.png'))
print('logo', lg.size)
