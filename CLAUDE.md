# CLAUDE.md

Monorepo de Transporte Rexcarga. Lee el README de la raíz y, antes de tocar
una parte, el CLAUDE.md de su carpeta:

- `landing/`: página pública en Cloudflare Pages (`transporterexcarga.com`).
- `conformes/`: app de conformes en Render (`conformes.transporterexcarga.com`).

## Decisiones (respétalas)

- **Un repo y un dominio, pero dos despliegues.** Los conformes necesitan
  Python (ReportLab, Pillow) y la landing tiene que ser gratis y no dormirse.
  No metas la landing en FastAPI ni sirvas los conformes bajo una ruta de la
  landing con proxy: la redirección `/conforme` basta.
- **Cada parte se despliega sola**: Render observa `conformes/**`
  (`render.yaml` en la raíz) y Pages observa `landing/*`. Un cambio en una
  parte no debe tocar la otra.
- **Marca compartida**: `--navy #0B2F5E` y `--red #D00F17`, y el logo nuevo.
  Si cambian, cambian en `landing/public/styles.css` y en
  `conformes/app/static/styles.css` a la vez. La tipografía sí es distinta a
  propósito: los conformes usan IBM Plex Mono para VIN, placas y folios.
- **Correo**: las dos partes usan Resend con el mismo dominio verificado.
- Los conformes son una herramienta interna: `noindex` y sin enlaces desde la
  landing.

## Estilo

Nombres, comentarios y commits en español. Sin frameworks ni pasos de build
en ninguna de las dos partes.
