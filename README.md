# Acta de Transferencia de Responsabilidad — MVP

Formulario web móvil-primero para transporte de carga rodada. El conductor
registra quién entrega y quién recibe las unidades (con firma), agrega las
unidades que necesite (VIN o placa + observaciones) y al enviar se genera un
PDF **con una hoja por unidad** que llega por correo al gerente y a los correos
de ambas partes. Sin base de datos, sin login: el objetivo es validar la idea.

## Cómo funciona

1. `GET /` sirve el formulario (FastAPI + Jinja2 + JS vanilla).
2. Las firmas se capturan en un `<canvas>` y viajan como PNG base64.
3. `POST /api/acta` valida en el servidor, genera el PDF (ReportLab, una hoja
   por unidad) y lo envía por Gmail SMTP a los tres destinatarios.
4. La respuesta trae el PDF en base64 para el botón **Descargar PDF** (respaldo
   si el correo fallara).

## Configurar el correo (Gmail)

1. Crea una cuenta Gmail dedicada, p. ej. `actas.transportexyz@gmail.com`.
2. Actívale **Verificación en dos pasos**.
3. Genera una **Contraseña de aplicación** (Cuenta Google → Seguridad →
   Contraseñas de aplicaciones). Son 16 caracteres.
4. Ponla en `GMAIL_APP_PASSWORD` (ver `.env.example`).

> El remitente (Gmail) y el servidor de envío (Google) quedan alineados, que es
> la mejor entregabilidad posible sin dominio propio. Límite ~500 correos/día.

## Correr localmente

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # y complétalo
set -a; source .env; set +a # exporta las variables
uvicorn app.main:app --reload
```

Abre http://localhost:8000 . Si aún no configuras el correo, el formulario
funciona y podrás **descargar el PDF**; el envío se activa al poner las
variables de Gmail.

## Desplegar en Render (gratis, sin dominio)

1. Sube el proyecto a un repositorio de GitHub.
2. En Render: **New → Web Service**, conecta el repo. `render.yaml` ya define
   build y start.
3. Carga las variables de entorno (`GMAIL_USER`, `GMAIL_APP_PASSWORD`,
   `MANAGER_EMAIL`, `COMPANY_NAME`).
4. Queda en `https://<tu-servicio>.onrender.com`.

### Mantenerla despierta (importante)

El plan gratis de Render **duerme la app tras ~15 min sin tráfico** y despertar
tarda 30–60 s. Para que la primera pantalla no salga lenta en el patio, crea un
cron externo (p. ej. cron-job.org) que le pegue cada 10 min a:

```
https://<tu-servicio>.onrender.com/health
```

## Logo del cliente (opcional)

Coloca un PNG en `app/static/logo.png` (o define `LOGO_PATH`). Si no hay logo,
el PDF simplemente lo omite.

## Estructura

```
app/
  main.py           # rutas FastAPI
  models.py         # validación (Pydantic) + chequeo de firma en blanco
  pdf_generator.py  # PDF, una hoja por unidad (ReportLab)
  emailer.py        # envío por Gmail SMTP
  config.py         # variables de entorno
  templates/index.html
  static/styles.css, app.js
requirements.txt · render.yaml · .env.example
```

## Alcance del MVP (y qué sigue)

Incluye: formulario móvil, firmas obligatorias, unidades dinámicas
colapsables, PDF una hoja por unidad, envío a tres correos, descarga de
respaldo. **No** incluye: persistencia, históricos, gestión de conductores o
viajes.


## Iniciar servidor

```bash
.venv/bin/uvicorn app.main:app --reload
```

La app carga el `.env` sola (ver `config.py`), así que no hace falta el
`set -a; source .env; set +a`. Lo que sí: si cambias un VALOR del `.env`, hay
que reiniciar — `--reload` vigila el código, no ese archivo.

Camino de evolución hacia un TMS: firma → (fotos de daños) → persistencia e
histórico → dominio y correo corporativo → gestión de conductores y viajes.
