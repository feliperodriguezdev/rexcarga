# Landing de Transporte Rexcarga

Página de una sola pantalla para `rexcarga.com`: presentación de la empresa,
servicios (niñera y grúa), galería, cobertura y formulario de cotización. El
formulario llega por correo a `programaciones.rexcarga@gmail.com`, y hay un
botón flotante de WhatsApp.

Alojamiento: **Cloudflare Pages** (gratis). El cliente solo paga el dominio.

## Estructura

```
public/                 # lo que se publica, tal cual (sin paso de build)
  index.html  styles.css  main.js  favicon.png
  img/                  # fotos ya optimizadas a WebP, sin metadatos
functions/
  api/cotizacion.js     # POST /api/cotizacion → correo por Resend
```

## Desplegar en Cloudflare Pages

1. Sube este repo a GitHub.
2. Cloudflare → **Workers & Pages → Create → Pages → Connect to Git**, elige
   el repo.
3. Configuración del build:
   - Framework preset: **None**
   - Build command: *(vacío)*
   - Build output directory: `public`
4. **Settings → Variables and Secrets** (en Production):
   - `RESEND_API_KEY`: secreto, de resend.com.
   - `MAIL_FROM`: `Rexcarga Web <cotizaciones@rexcarga.com>`.
   - `MAIL_TO`: `programaciones.rexcarga@gmail.com` (acepta varios separados
     por coma).
5. **Custom domains**: añade `rexcarga.com` y `www.rexcarga.com`. Como el
   dominio está comprado en Cloudflare, los registros DNS se crean solos.

Cada push a `master` publica. Las ramas generan URLs de vista previa.

## Correo (Resend)

Para que `MAIL_FROM` pueda ser `@rexcarga.com`, el dominio tiene que estar
verificado en Resend: **Domains → Add domain**, y se copian a Cloudflare DNS
los registros que pide (SPF, DKIM). Hasta entonces el formulario responde con
error, y la página le ofrece al cliente enviar los mismos datos por WhatsApp,
así que no se pierde ninguna solicitud.

Cada correo trae el `Reply-To` del cliente (con "Responder" se le contesta a
él) y un botón para abrirle WhatsApp.

## Probar en local

La página es estática: basta con

```bash
cd public && python3 -m http.server 8000
```

El formulario necesita la función. `npx wrangler pages dev public` la corre,
con las variables en `.dev.vars` (ver `.dev.vars.example`). **Ojo:** el
runtime de Wrangler exige glibc 2.35+, y Ubuntu 20.04 no la trae. Ahí la
función se prueba importándola desde Node con `fetch` simulado, o
directamente en una URL de vista previa de Pages.

## Cambiar contenido

- **Textos**: directo en `index.html`. Salen de la propuesta del cliente
  (`landing-rexcarga.docx`).
- **Número de WhatsApp y mensaje**: constantes al principio de `main.js`.
- **Fotos de la galería**: `public/img/galeria/01.webp … 14.webp`. Si cambia
  la cantidad, actualiza `FOTOS_GALERIA` en `main.js`. Para optimizar fotos
  nuevas: máximo 1200 px de ancho, WebP calidad ~75, sin EXIF.
