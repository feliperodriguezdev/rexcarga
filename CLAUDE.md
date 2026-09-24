# CLAUDE.md

Contexto para trabajar este proyecto con Claude Code. Léelo antes de modificar código.

## Qué es

MVP web para una empresa de transporte de carga rodada (niñeras y grúas). Un
conductor registra la **transferencia de responsabilidad** de vehículos: quién
entrega y quién recibe (con firma), y las unidades transferidas. Al enviar se
genera un PDF y se envía por correo. El objetivo es validar la idea para luego
evolucionar hacia un TMS.

**Vocabulario**: de cara al usuario el documento se llama **conforme**
(interfaz, título del PDF, asunto del correo y nombre del archivo). En el
código los identificadores siguen siendo `acta` — `ActaRequest`, `/api/acta`,
`enviar_acta`, la variable `acta` — y se quedan así a propósito: renombrarlos
no aporta y sí rompe el contrato.

**Sin base de datos, sin login, sin históricos.** No agregues persistencia,
autenticación ni gestión de conductores/viajes salvo que se pida de forma
explícita: es una decisión de alcance, no un olvido.

## Stack

- Backend: **FastAPI** (Python 3.12), servido con uvicorn.
- Frontend: **HTML + CSS + JS vanilla** servido por FastAPI (Jinja2 para el
  index, estáticos en `app/static`). Sin framework, sin paso de build.
- PDF: **ReportLab** (canvas de bajo nivel, no platypus completo).
- Imágenes/firmas: **Pillow**.
- Correo: **dos transportes intercambiables** en `emailer.py`. Con
  `RESEND_API_KEY` se envía por HTTPS (Resend); sin ella, por Gmail SMTP.
  Producción usa Resend por obligación: Render free bloquea los puertos SMTP.
  Local usa SMTP para no exigir clave de Resend al desarrollar.
- Despliegue: **Render** free tier (`render.yaml` incluido).

## Estructura

```
app/
  main.py           # rutas: GET /, POST /api/acta, GET /health
  models.py         # Pydantic: ActaRequest, Parte, Unidad + decodificar_firma()
  pdf_generator.py  # generar_pdf(): UNA HOJA POR UNIDAD (canvas ReportLab)
  emailer.py        # enviar_acta(): Gmail SMTP, 3 destinatarios
  config.py         # variables de entorno (secretos, correo gerente, empresa, logo)
  templates/index.html   # formulario + pantalla de éxito (misma página)
  static/styles.css      # tokens de diseño (acero/ámbar), móvil-primero
  static/app.js          # firmas en canvas, unidades dinámicas, envío, éxito
requirements.txt · render.yaml · .env.example · README.md
```

## Comandos

```bash
# entorno
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# correr en local (sin correo funciona; deja descargar el PDF)
cp .env.example .env          # completar variables
set -a; source .env; set +a
uvicorn app.main:app --reload # http://localhost:8000
```

No hay suite de tests formal todavía. Para probar cambios rápido se usa
`fastapi.testclient.TestClient` en un script suelto, y para revisar el PDF se
rasteriza con `pdftoppm -png -r 110 salida.pdf pag` y se mira el PNG.

## Contrato de datos (POST /api/acta)

El navegador manda JSON; el servidor valida TODO (no confíes en el cliente).

```json
{
  "lugar": "str obligatorio",
  "transporte_tipo": "ninera|grua|rodado",
  "transporte_placa": "str obligatorio, alfanumérico, máx 6",
  "entrega": { "nombre", "tipo_documento": "CC|CE|PAS|NIT", "documento",
               "email", "firma": "data:image/png;base64,..." },
  "recibe":  { ...igual que entrega... },
  "unidades": [ { "identificador_tipo": "vin|placa",
                  "identificador", "observacion",
                  "fotos": ["data:image/jpeg;base64,..."] } ]   // mínimo 1 unidad;
                                                               // fotos opcionales
}
```

Respuesta OK: `{ ok, folio, email_ok, email_error, pdf_base64, filename }`.
El `pdf_base64` alimenta el botón "Descargar PDF" (respaldo si el correo falla).

## Reglas del dominio (spec congelado — respétalas)

- **Un acta = un evento**: quien entrega y quien recibe firman la misma acta,
  en el mismo lugar y momento, sobre las mismas unidades. No hay "modo entrega"
  vs "modo recepción".
- **PDF: una hoja por unidad.** N unidades → N páginas. Cada hoja es un acta
  autónoma: encabezado (logo, folio, "Unidad X de N", fecha, lugar, vehículo de
  transporte), datos de ambas partes arriba, la unidad + su observación, y las
  dos firmas abajo.
- **Firmas obligatorias** para ambas partes. Se capturan UNA vez y se
  reutilizan en todas las hojas. `decodificar_firma()` en `models.py` rechaza
  el canvas en blanco (mínimo de píxeles con tinta).
- **Observación obligatoria** por unidad; el formulario la pre-llena con
  "Sin observaciones" (editable/borrable), para ahorrarle escritura al conductor.
- **Vehículo que hace el movimiento**: obligatorio. Tipo (`ninera`, `grua` o
  `rodado` — este último es la unidad moviéndose por sus propios medios) más su
  placa, alfanumérica de máximo 6 caracteres, guardada en mayúsculas y sin
  separadores. El formulario la limpia mientras se escribe en vez de usar
  `maxlength`: con el tope del navegador, pegar "ABC-123" dejaría "ABC-12" y de
  ahí "ABC12", una placa distinta y sin aviso, en un documento que se firma.
- **Dos botones de foto, no uno**: "Tomar foto" (`capture="environment"`, sin
  `multiple`) y "Galería" (`multiple`, sin `capture`). Con un solo input, el
  selector de fotos de Android abre el álbum del sistema y NO ofrece cámara,
  que es justo lo que este módulo necesita. No los unifiques.
- **Fotos por unidad**: opcionales, sin límite de cantidad de cara al
  conductor. El navegador las reduce ANTES de subirlas (`app.js`) y baja de
  nivel de compresión solo si el conforme se acerca al presupuesto de 8 MB:
  el conductor nunca decide esto en el patio. Pasarlas por un canvas las
  despoja de metadatos, incluida la ubicación GPS. En el PDF van como tira de
  miniaturas en la hoja de su unidad (una fila de 4 grandes, o dos filas más
  pequeñas si hay más); en tamaño completo viajan como adjuntos del correo.
  Los topes de `models.py` (15 por unidad, 2 MB cada una, 20 MB por acta) no
  son límites de producto sino válvulas contra un cliente malicioso.
  Nota de dominio: una niñera carga 9 unidades como máximo y el conforme
  registra UNA placa de transporte, así que el acta tiene techo físico propio.
- **Identificador**: VIN o placa (al menos uno por unidad). NO se validan los
  17 caracteres del VIN (los carros nuevos suelen ir solo con VIN). Se guarda
  en mayúsculas.
- **Folio y fecha/hora los pone el servidor** (`TR-AAAAMMDD-XXXX`, zona
  America/Bogota). No viajan en el payload; no confíes en la hora del celular.
- **Correo del gerente**: hardcodeado por variable de entorno (`MANAGER_EMAIL`),
  no viaja en el payload. Se envía a gerente + entrega + recibe (sin duplicados).

## Configuración (variables de entorno)

`MANAGER_EMAIL`, `COMPANY_NAME`, opcional `LOGO_PATH` (PNG; si no existe, el
PDF omite el logo) y `TIMEZONE`.

Del correo, según el transporte: `RESEND_API_KEY` + `MAIL_FROM` para HTTPS, o
`GMAIL_USER` + `GMAIL_APP_PASSWORD` para SMTP. `missing_email_config()` solo
exige las del transporte activo: pedir las cuatro haría que producción se
quejara de credenciales que no va a usar.
Nunca pongas la app password ni ningún secreto en el frontend ni en el repo.

## Decisiones de diseño (frontend)

- Móvil-primero, tap targets de ~52px, barra de acción fija abajo.
- Paleta **tomada del logo del cliente**: azul `--navy #18446F` (el 71% de su
  tinta) y rojo `--red #C11C1E`. El azul manda en el chrome y el texto
  (`--ink` es ese azul llevado a casi negro); el rojo se gasta solo en la
  acción primaria. El resto, gris disciplinado. Reemplazó al ámbar de
  seguridad original; si se revende a otro cliente, hay que volver a derivar
  estos dos tokens de SU logo.
- **La barra superior es clara a propósito.** Lleva el logo, y el logo es azul
  sobre fondo transparente: sobre una barra oscura la niñera desaparecería.
  Por eso el fondo es blanco con borde inferior, y `theme-color` acompaña.
- El rojo de la marca y el `--danger` de validación conviven porque son
  componentes distintos: el primario es un bloque sólido en la barra fija de
  abajo, y los errores son un panel rosado con texto vino más un anillo en el
  campo. No los unifiques.
- Tipografía: IBM Plex Sans (UI) + IBM Plex Mono (VIN/placa y folio — son
  códigos donde importa distinguir 0/O, 1/I).
- **Las firmas van al final del formulario**, en su propia tarjeta después de
  las unidades — no dentro de los datos de cada parte. Firmar antes de
  diligenciar las unidades equivale a firmar un cheque en blanco. La tarjeta
  repite el nombre de cada parte junto al recuadro, porque ahí ya no se ve a
  quién corresponde. Los errores de firma se listan de últimas, siguiendo el
  orden visual.
- **La observación crece con su contenido**: arranca en 3 líneas (`rows="3"`)
  y se estira sola, sin barra interna ni tirador de redimensionar. Ojo con dos
  trampas al tocar esto: hay que remedir tras `document.fonts.ready` (IBM Plex
  Sans llega por red después del primer render y es más ancha que la fuente de
  reserva, así que el texto reenvuelve y quedaría cortado), y no se puede medir
  una unidad colapsada (`display:none` da alto 0), por eso se reajusta al
  expandirla.
- Unidades colapsables; al enviar con éxito se muestra pantalla de confirmación
  con folio, botón Descargar PDF y botón "Nueva acta" (recarga limpia).

## Limitaciones conocidas / buenos primeros cambios

- **Observación muy larga**: se recorta con `Paragraph.split()` y se deja un
  aviso en el log. OJO con la creencia anterior: `drawOn` NO recorta — pinta el
  párrafo entero hacia arriba desde su base, así que un texto que no cabe se
  montaba encima de su propia etiqueta y del título de la unidad. Capacidad
  actual: ~21 líneas sin fotos, ~13 con cuatro, ~10 con ocho. Si hiciera falta
  más, habría que paginar la observación dentro de la misma unidad.
- **Geometría vertical del PDF**: vive en constantes al principio de
  `pdf_generator.py` (`_BASE_FIRMAS`, `_ALTO_BLOQUE_FIRMA`, `_TOPE_CONTENIDO`…)
  y están ligadas entre sí: el suelo del contenido se DEDUCE de dónde se apoyan
  las firmas más su altura. Antes eran números sueltos repartidos por el código
  y eso ya causó un solape. No vuelvas a escribir un milímetro a mano.
- **Logo**: ya cableado en `app/static/logo.png` (la ruta por defecto de
  `LOGO_PATH`), así que no necesita variable de entorno ni en Render. El
  original del cliente queda en `app/images/logo.jpeg`; el PNG se derivó de
  ahí recortando el margen, volviendo transparente el fondo (era un gris
  viñeteado que se veía como recuadro sobre la hoja) y cuantizando a 32
  colores. Para otro cliente, repetir esa receta: el JPEG crudo mete ruido
  que multiplica por diez el peso del PDF que viaja por correo.
- **Sin rate-limit** en `/api/acta`. Para producción conviene uno básico.
- **Render free BLOQUEA la salida SMTP** (puertos 25, 465 y 587). RESUELTO
  enviando por HTTPS con Resend; queda aquí porque el síntoma vuelve a
  aparecer si alguien reactiva el camino SMTP en producción. La traza engaña — `smtplib` lanza
  solo la primera excepción de `socket.create_connection` y ahí aparece un
  `Network is unreachable` de IPv6 que hace pensar en un problema de red. El
  síntoma real es **timeout en IPv4 contra 465 y 587, con HTTPS conectando
  normal**. Medido el 2026-09-14 contra el servicio en vivo. Salidas: subir a
  cualquier instancia de pago de Render (lo que ellos recomiendan), o enviar
  por HTTPS con un proveedor de correo, que es el camino natural cuando se
  llegue al escalón de dominio propio.
- Render free duerme la app tras ~15 min; se mitiga con un cron externo a
  `/health` (ver README). Una instancia de pago quita este problema y el del
  SMTP de una vez.

## Estilo de código

- Nombres y comentarios en español (dominio en español).
- Prosa clara sobre cleverness; funciones cortas y con una responsabilidad.
- La validación vive en el servidor (`models.py`), no solo en el cliente.
- Mantén el frontend sin dependencias/build mientras sea un MVP.

## Rumbo de evolución (para dimensionar cambios)

firma → (fotos de daños por unidad) → persistencia e histórico → dominio y
correo corporativo → gestión de conductores y viajes → TMS. Cada escalón es un
punto de monetización; no adelantes escalones sin que se pidan.
