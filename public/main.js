// Landing de Rexcarga: menú móvil, carrusel, WhatsApp y formulario de cotización.
(() => {
  "use strict";

  const WHATSAPP_NUMERO = "573017599061";
  const WHATSAPP_MENSAJE = "Hola, estoy interesado en cotizar el servicio de transporte de vehículos. Agradezco su asesoría.";
  const FOTOS_GALERIA = 14;

  const enlaceWhatsapp = (texto) =>
    `https://wa.me/${WHATSAPP_NUMERO}?text=${encodeURIComponent(texto)}`;

  // --- WhatsApp: todos los botones abren el chat con el mensaje predeterminado
  document.querySelectorAll(".js-whatsapp").forEach((a) => {
    a.href = enlaceWhatsapp(WHATSAPP_MENSAJE);
    a.target = "_blank";
    a.rel = "noopener";
  });

  // --- Cabecera: sombra al hacer scroll y menú móvil
  const cabecera = document.getElementById("cabecera");
  const botonMenu = document.getElementById("boton-menu");
  const navegacion = document.getElementById("navegacion");

  const actualizarSombra = () => cabecera.classList.toggle("con-sombra", window.scrollY > 8);
  window.addEventListener("scroll", actualizarSombra, { passive: true });
  actualizarSombra();

  const cerrarMenu = () => {
    navegacion.classList.remove("abierta");
    botonMenu.setAttribute("aria-expanded", "false");
    botonMenu.setAttribute("aria-label", "Abrir menú");
  };
  botonMenu.addEventListener("click", () => {
    const abierto = navegacion.classList.toggle("abierta");
    botonMenu.setAttribute("aria-expanded", String(abierto));
    botonMenu.setAttribute("aria-label", abierto ? "Cerrar menú" : "Abrir menú");
  });
  navegacion.addEventListener("click", (e) => { if (e.target.closest("a")) cerrarMenu(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") cerrarMenu(); });

  // --- Galería
  const galeria = document.getElementById("galeria");
  for (let i = 1; i <= FOTOS_GALERIA; i++) {
    const n = String(i).padStart(2, "0");
    const figura = document.createElement("figure");
    figura.innerHTML = `<img src="img/galeria/${n}.webp" alt="Operación de Rexcarga, foto ${i} de ${FOTOS_GALERIA}" width="1200" height="900" loading="lazy">`;
    galeria.appendChild(figura);
  }
  document.querySelectorAll(".flecha").forEach((boton) => {
    boton.addEventListener("click", () => {
      const paso = galeria.querySelector("figure").offsetWidth + 16;
      galeria.scrollBy({ left: paso * Number(boton.dataset.direccion) });
    });
  });

  // --- Aparición suave de bloques al entrar en pantalla
  const bloques = document.querySelectorAll(".valores li, .ventaja, .servicio, .recuadro, .foto-marco, .mapa");
  if ("IntersectionObserver" in window) {
    const observador = new IntersectionObserver((entradas) => {
      entradas.forEach((e) => {
        if (e.isIntersecting) { e.target.classList.add("visible"); observador.unobserve(e.target); }
      });
    }, { rootMargin: "0px 0px -60px 0px" });
    bloques.forEach((b) => { b.classList.add("revelar"); observador.observe(b); });
  }

  // --- Formulario de cotización
  const formulario = document.getElementById("formulario");
  const errores = document.getElementById("errores");
  const exito = document.getElementById("exito");
  const botonEnviar = document.getElementById("boton-enviar");
  const condicion = document.getElementById("condicion");
  const campoOtra = document.getElementById("campo-otra");
  const fecha = document.getElementById("fecha");

  // La fecha mínima es hoy, en hora local (toISOString daría la de UTC)
  const hoy = new Date();
  fecha.min = new Date(hoy.getTime() - hoy.getTimezoneOffset() * 60000).toISOString().slice(0, 10);

  condicion.addEventListener("change", () => {
    const otra = condicion.value === "Otra condición";
    campoOtra.hidden = !otra;
    document.getElementById("condicion_otra").required = otra;
  });

  // Los botones "Cotiza" de cada servicio dejan el tipo preseleccionado
  document.querySelectorAll("[data-servicio]").forEach((a) => {
    a.addEventListener("click", () => { document.getElementById("servicio").value = a.dataset.servicio; });
  });

  const ETIQUETAS = {
    nombre: "Nombres y apellidos", celular: "Celular", email: "Correo electrónico",
    origen: "Ciudad de origen", destino: "Ciudad de destino", vehiculo: "Marca y modelo del vehículo",
    fecha: "Fecha estimada del traslado", servicio: "Tipo de servicio",
    condicion: "Condición especial", condicion_otra: "Especificación de la condición",
  };

  function validar(datos) {
    const faltan = [];
    formulario.querySelectorAll(".campo").forEach((c) => c.classList.remove("invalido"));
    for (const [nombre, etiqueta] of Object.entries(ETIQUETAS)) {
      const control = formulario.elements[nombre];
      if (!control.required) continue;
      let malo = !datos[nombre];
      if (!malo && nombre === "email") malo = !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(datos.email);
      if (!malo && nombre === "celular") malo = datos.celular.replace(/\D/g, "").length < 7;
      if (!malo && nombre === "fecha") malo = datos.fecha < fecha.min;
      if (malo) { faltan.push({ nombre, etiqueta }); control.closest(".campo").classList.add("invalido"); }
    }
    return faltan;
  }

  function mostrarErrores(html) {
    errores.innerHTML = html;
    errores.hidden = false;
    errores.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  // Si el envío falla, el cliente no pierde lo que escribió: se lo llevamos a WhatsApp
  function resumenWhatsapp(d) {
    const cond = d.condicion === "Otra condición" ? `Otra: ${d.condicion_otra}` : d.condicion;
    return [
      "Hola, quiero cotizar un traslado:",
      `• Nombre: ${d.nombre}`, `• Celular: ${d.celular}`, `• Correo: ${d.email}`,
      `• Origen: ${d.origen}`, `• Destino: ${d.destino}`, `• Vehículo: ${d.vehiculo}`,
      `• Fecha estimada: ${d.fecha}`, `• Servicio: ${d.servicio}`, `• Condición: ${cond}`,
    ].join("\n");
  }

  formulario.addEventListener("submit", async (e) => {
    e.preventDefault();
    errores.hidden = true;
    const datos = Object.fromEntries(
      [...new FormData(formulario)].map(([k, v]) => [k, String(v).trim()])
    );

    const faltan = validar(datos);
    if (faltan.length) {
      mostrarErrores(`Revisa estos campos:<ul>${faltan.map((f) => `<li>${f.etiqueta}</li>`).join("")}</ul>`);
      formulario.elements[faltan[0].nombre].focus({ preventScroll: true });
      return;
    }

    botonEnviar.disabled = true;
    botonEnviar.textContent = "Enviando…";
    try {
      const respuesta = await fetch("api/cotizacion", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(datos),
      });
      const cuerpo = await respuesta.json().catch(() => ({}));
      if (!respuesta.ok || !cuerpo.ok) throw new Error(cuerpo.error || "No se pudo enviar");
      formulario.hidden = true;
      exito.hidden = false;
      exito.focus();
    } catch {
      const enlace = enlaceWhatsapp(resumenWhatsapp(datos));
      mostrarErrores(`No pudimos enviar tu solicitud en este momento. <a href="${enlace}" target="_blank" rel="noopener">Envíala por WhatsApp</a> con los datos ya escritos, o inténtalo de nuevo en unos minutos.`);
    } finally {
      botonEnviar.disabled = false;
      botonEnviar.textContent = "Solicitar mi cotización";
    }
  });

  document.getElementById("anio").textContent = new Date().getFullYear();
})();
