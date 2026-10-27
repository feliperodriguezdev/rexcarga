# Rexcarga

Proyecto web de Transporte Rexcarga S.A.S. Un solo repositorio y un solo
dominio, con dos partes que se despliegan cada una donde le conviene:

| Carpeta | Qué es | Dónde corre | URL |
|---|---|---|---|
| `landing/` | Página pública + formulario de cotización (estático + una función JS) | Cloudflare Pages, gratis | `transporterexcarga.com` |
| `conformes/` | App de conformes de transferencia: firmas, fotos, PDF por correo (FastAPI) | Render | `conformes.transporterexcarga.com` |

`transporterexcarga.com/conforme` redirige a los conformes (`landing/public/_redirects`).

**Por qué dos despliegues:** los conformes generan PDF con ReportLab y Pillow,
que necesitan un servidor Python, y Cloudflare Pages no lo da. Llevar la
landing a Render la haría dormirse en el plan gratis: el primer cliente
potencial del día esperaría un minuto frente a una página en blanco. Así la
landing sigue gratis y rápida, y los conformes no cambian.

Cada parte tiene su README y su CLAUDE.md con los detalles.

## Puesta en producción

### 1. Dominio (el cliente)

Comprar `transporterexcarga.com` en Cloudflare, a nombre de la empresa, y
agregar a Felipe como miembro de la cuenta. **Los subdominios no cuestan
nada**: vienen con el dominio.

### 2. Landing → Cloudflare Pages

Ver `landing/README.md`. En resumen: conectar este repo, con root directory
`landing`, salida `public`, sin build y con build watch path `landing/*`.
Luego, en *Custom domains*, `transporterexcarga.com` y `www.`.

### 3. Conformes → Render

`render.yaml` está en la raíz y ya trae `rootDir: conformes`. Para un servicio
nuevo, *New → Blueprint* desde este repo. Si el servicio viejo sigue
suspendido, ver "Reactivar" en `conformes/README.md`.

Subdominio, en dos sitios y una sola vez:

1. **Render** → servicio → *Settings → Custom Domains* → añadir
   `conformes.transporterexcarga.com`. El plan gratis lo permite y el
   certificado HTTPS se emite solo.
2. **Cloudflare** → *DNS → Records* → añadir:
   - Tipo `CNAME`, nombre `conformes`, destino `<servicio>.onrender.com`.
   - Proxy: empieza en **DNS only** (nube gris) hasta que Render verifique el
     dominio y emita el certificado. Después se puede pasar a *Proxied* con
     SSL/TLS en **Full**, lo que permite ponerle a `/api/acta` la regla
     gratuita de rate-limit de Cloudflare.

### 4. Correo → Resend (compartido)

Las dos partes envían por Resend desde el mismo dominio. Se verifica
`transporterexcarga.com` en Resend **una sola vez** (*Domains → Add domain*,
y se copian a Cloudflare DNS los registros SPF y DKIM que pide). Remitentes:

- Landing: `MAIL_FROM = Rexcarga Web <cotizaciones@transporterexcarga.com>`
- Conformes: `MAIL_FROM = conformes@transporterexcarga.com`

Puede ser la misma `RESEND_API_KEY` para las dos, o una por parte para poder
revocarlas por separado.

## Costos

- Dominio: lo paga el cliente, cada año.
- Cloudflare Pages y Resend (hasta 3.000 correos/mes): gratis.
- Render: gratis, pero la app se duerme tras ~15 min y el primer conforme
  tarda en abrir (se mitiga con un cron a `/health`). Starter, ~7 USD/mes,
  quita la espera.

## Historia

Los dos proyectos nacieron en repos separados (`rexcarga-landing` y
`conforme`) y se unieron aquí el 2026-10-26 con `git subtree`, conservando su
historia. El tag `conformes-mvp-v1` marca la versión de los conformes que
estuvo en producción antes de la pausa de octubre de 2026.
