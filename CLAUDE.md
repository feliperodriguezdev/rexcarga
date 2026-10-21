# CLAUDE.md

Landing de Transporte Rexcarga (transporte de vehículos en niñera y grúa,
Colombia). Lee el README para el despliegue.

## Estado (2026-10-19)

La landing está terminada y subida a GitHub como repo privado
(`feliperodriguezdev/rexcarga-landing`). Las fotos ya tienen las placas
difuminadas; Felipe las editó a mano. La edición de fotos la hace él, no
Claude. Todavía no está publicada. Pendiente, en orden:

1. Crear el proyecto en Cloudflare Pages desde el repo: preset None, build
   vacío, salida `public`. Puede hacerse ya, con la URL `*.pages.dev`.
2. El cliente compra `rexcarga.com` en Cloudflare y agrega a Felipe como
   miembro de su cuenta.
3. Verificar el dominio en Resend y cargar `RESEND_API_KEY`, `MAIL_FROM` y
   `MAIL_TO` en Pages. Luego, conectar el dominio propio.

## Decisiones (respétalas)

- **Rutas relativas** (`img/...`, `styles.css`, `api/cotizacion`), nunca con
  `/` al inicio. En GitHub Pages el sitio vive en la subcarpeta
  `/rexcarga-landing/`, y una ruta con `/` apunta a la raíz del dominio, donde
  no existe nada.

- **Cloudflare Pages, sin build.** `public/` se publica tal cual y
  `functions/` son las Pages Functions. HTML, CSS y JS vanilla, sin framework
  ni dependencias. El cliente pidió no pagar alojamiento.
- **El formulario envía por Resend** desde `functions/api/cotizacion.js`, y el
  servidor valida todo. Si el envío falla, el front le ofrece al cliente
  WhatsApp con los datos ya escritos: nunca debe perderse una solicitud.
- **Trampa anti-bots**: el campo oculto `sitio_web`. Si viene lleno, se
  responde ok y no se envía nada. Si llega spam real, el siguiente paso es
  Cloudflare Turnstile (gratis).
- **Paleta del logo**: `--navy #0B2F5E` y `--red #D00F17`. El rojo es solo
  para la acción primaria. El verde de WhatsApp es el del botón de WhatsApp,
  no parte de la marca.
- **Estilo inspirado en horizonautologistics.com** (Plus Jakarta Sans,
  antetítulos con raya, numeración "01.", bloques sobrios). Es referencia, no
  copia: no uses textos ni imágenes de ese sitio.
- **Textos**: salen de la propuesta del cliente. No inventes cifras, clientes
  ni testimonios: lo único cuantitativo que dieron es "más de seis años".
- **Fotos**: reales del cliente, en WebP, sin metadatos. Se descartaron las
  que traen marcas de agua con fecha y coordenadas GPS, y los banners con
  texto incrustado.

## Relación con el repo `conforme`

El servicio de conformes, en `../conforme`, está en pausa por decisión del
cliente. Esta landing es un proyecto aparte: no los mezcles.

## Estilo de código

Nombres y comentarios en español. CSS con tokens en `:root`, móvil-primero y
tap targets de ~52px.
