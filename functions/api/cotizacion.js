// POST /api/cotizacion — Cloudflare Pages Function.
// Valida la solicitud de cotización y la envía por correo con Resend.
// Variables (Pages → Settings → Variables and Secrets):
//   RESEND_API_KEY  secreto de resend.com
//   MAIL_FROM       remitente de un dominio verificado en Resend,
//                   p. ej. "Rexcarga Web <cotizaciones@rexcarga.com>"
//   MAIL_TO         buzón que recibe las cotizaciones

const SERVICIOS = ["Transporte en niñera", "Servicio de grúa – Urbano", "Servicio de grúa – Nacional"];
const CONDICIONES = ["Ninguna", "Blindado", "Modificado", "No funciona", "Otra condición"];

// Topes de longitud: el formulario ya los pone, pero no confiamos en el cliente
const CAMPOS = {
  nombre: 120, celular: 20, email: 160, origen: 80, destino: 80,
  vehiculo: 120, fecha: 10, servicio: 40, condicion: 40, condicion_otra: 500,
};

const responder = (cuerpo, estado = 200) =>
  new Response(JSON.stringify(cuerpo), {
    status: estado,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });

const escapar = (s) =>
  s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

function limpiar(entrada) {
  const datos = {};
  for (const [campo, tope] of Object.entries(CAMPOS)) {
    // Sin saltos de línea: varios campos van al asunto del correo
    const valor = typeof entrada[campo] === "string" ? entrada[campo].replace(/\s+/g, " ").trim() : "";
    datos[campo] = valor.slice(0, tope);
  }
  return datos;
}

function validar(d) {
  const errores = [];
  for (const campo of ["nombre", "celular", "email", "origen", "destino", "vehiculo", "fecha"]) {
    if (!d[campo]) errores.push(`Falta ${campo}`);
  }
  if (d.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(d.email)) errores.push("Correo inválido");
  if (d.celular && d.celular.replace(/\D/g, "").length < 7) errores.push("Celular inválido");
  if (d.fecha && !/^\d{4}-\d{2}-\d{2}$/.test(d.fecha)) errores.push("Fecha inválida");
  if (!SERVICIOS.includes(d.servicio)) errores.push("Tipo de servicio inválido");
  if (!CONDICIONES.includes(d.condicion)) errores.push("Condición inválida");
  if (d.condicion === "Otra condición" && !d.condicion_otra) errores.push("Falta especificar la condición");
  return errores;
}

function armarCorreo(d) {
  const condicion = d.condicion === "Otra condición" ? `Otra: ${d.condicion_otra}` : d.condicion;
  const filas = [
    ["Nombre", d.nombre], ["Celular", d.celular], ["Correo", d.email],
    ["Origen", d.origen], ["Destino", d.destino], ["Vehículo", d.vehiculo],
    ["Fecha estimada", d.fecha], ["Servicio", d.servicio], ["Condición", condicion],
  ];
  const celular = d.celular.replace(/\D/g, "");
  const whatsapp = `https://wa.me/${celular.length === 10 ? "57" + celular : celular}`;

  const html = `
    <div style="font-family:Arial,sans-serif;color:#0E1B2E;max-width:560px">
      <h2 style="color:#0B2F5E;margin:0 0 4px">Nueva solicitud de cotización</h2>
      <p style="color:#5b6575;margin:0 0 20px">Recibida desde rexcarga.com</p>
      <table style="border-collapse:collapse;width:100%">
        ${filas.map(([k, v]) => `
          <tr>
            <td style="padding:8px 12px;background:#F2F4F7;font-weight:bold;width:150px;border-bottom:1px solid #fff">${k}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #F2F4F7">${escapar(v)}</td>
          </tr>`).join("")}
      </table>
      <p style="margin:24px 0 0">
        <a href="${whatsapp}" style="background:#1FA855;color:#fff;padding:12px 20px;border-radius:6px;text-decoration:none;font-weight:bold">Responder por WhatsApp</a>
      </p>
      <p style="color:#5b6575;font-size:13px;margin-top:20px">Para responder por correo, usa "Responder": va directo al cliente.</p>
    </div>`;
  const texto = filas.map(([k, v]) => `${k}: ${v}`).join("\n");
  return { html, texto, asunto: `Cotización: ${d.origen} → ${d.destino} · ${d.servicio} · ${d.nombre}` };
}

export async function onRequestPost({ request, env }) {
  let entrada;
  try {
    entrada = await request.json();
  } catch {
    return responder({ ok: false, error: "Solicitud inválida" }, 400);
  }

  // Trampa para bots: una persona nunca ve ni llena este campo. Se responde
  // ok para que el bot no aprenda a esquivarla.
  if (entrada.sitio_web) return responder({ ok: true });

  const datos = limpiar(entrada);
  const errores = validar(datos);
  if (errores.length) return responder({ ok: false, error: errores.join(". ") }, 400);

  if (!env.RESEND_API_KEY || !env.MAIL_FROM || !env.MAIL_TO) {
    console.error("Faltan variables de correo: RESEND_API_KEY, MAIL_FROM o MAIL_TO");
    return responder({ ok: false, error: "Correo no configurado" }, 503);
  }

  const correo = armarCorreo(datos);
  const envio = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${env.RESEND_API_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      from: env.MAIL_FROM,
      to: env.MAIL_TO.split(",").map((s) => s.trim()),
      reply_to: datos.email,
      subject: correo.asunto,
      html: correo.html,
      text: correo.texto,
    }),
  });

  if (!envio.ok) {
    console.error("Resend rechazó el envío", envio.status, await envio.text());
    return responder({ ok: false, error: "No se pudo enviar el correo" }, 502);
  }
  return responder({ ok: true });
}
