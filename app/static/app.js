"use strict";

// Cada carga empieza arriba: este formulario se llena de principio a fin y
// "Nuevo conforme" recarga la página, así que restaurar el scroll estorba.
if ("scrollRestoration" in history) history.scrollRestoration = "manual";

// ---------- Firmas en canvas ----------
class PadFirma {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.dibujado = false;
    this._ajustar();
    this._bind();
    window.addEventListener("resize", () => this._ajustar());
  }
  _ajustar() {
    // Escala por densidad de pantalla para trazo nítido.
    const rect = this.canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const prev = this.dibujado ? this.canvas.toDataURL() : null;
    this.canvas.width = Math.round(rect.width * dpr);
    this.canvas.height = Math.round(rect.height * dpr);
    this.ctx.scale(dpr, dpr);
    this.ctx.lineWidth = 2.2;
    this.ctx.lineCap = "round";
    this.ctx.lineJoin = "round";
    this.ctx.strokeStyle = "#16202B";
    if (prev) {
      const img = new Image();
      img.onload = () => this.ctx.drawImage(img, 0, 0, rect.width, rect.height);
      img.src = prev;
    }
  }
  _pos(e) {
    const r = this.canvas.getBoundingClientRect();
    const t = e.touches ? e.touches[0] : e;
    return { x: t.clientX - r.left, y: t.clientY - r.top };
  }
  _bind() {
    let dibujando = false;
    const start = (e) => { e.preventDefault(); dibujando = true; const p = this._pos(e);
      this.ctx.beginPath(); this.ctx.moveTo(p.x, p.y); };
    const move = (e) => { if (!dibujando) return; e.preventDefault(); const p = this._pos(e);
      this.ctx.lineTo(p.x, p.y); this.ctx.stroke(); this.dibujado = true; };
    const end = () => { dibujando = false; };
    this.canvas.addEventListener("pointerdown", start);
    this.canvas.addEventListener("pointermove", move);
    window.addEventListener("pointerup", end);
  }
  limpiar() {
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    this.dibujado = false;
  }
  vacio() { return !this.dibujado; }
  dataUrl() { return this.canvas.toDataURL("image/png"); }
}

const pads = {
  entrega: new PadFirma(document.querySelector('[data-canvas="entrega"]')),
  recibe: new PadFirma(document.querySelector('[data-canvas="recibe"]')),
};
document.querySelectorAll("[data-clear]").forEach((b) =>
  b.addEventListener("click", () => pads[b.dataset.clear].limpiar())
);

// La tarjeta de firmas está lejos de los datos de cada parte: repetimos ahí
// el nombre que se escribió arriba para que nadie firme en el recuadro ajeno.
["entrega", "recibe"].forEach((rol) => {
  const campo = document.querySelector(`[data-parte="${rol}"] [data-k="nombre"]`);
  const eco = document.querySelector(`[data-firma-nombre="${rol}"]`);
  const pintar = () => { eco.textContent = campo.value.trim(); };
  campo.addEventListener("input", pintar);
  pintar();
});

// ---------- Tipo de transporte y su placa ----------
const ETIQUETA_PLACA = {
  ninera: "Placa de la niñera",
  grua: "Placa de la grúa",
  rodado: "Placa del vehículo",
};
const MAX_PLACA = 6;

const segTransporte = document.getElementById("seg-transporte");
const labelPlaca = document.getElementById("label-transporte-placa");
const inputPlaca = document.getElementById("transporte-placa");
let transporteTipo = "ninera";

segTransporte.querySelectorAll(".seg-btn").forEach((b) =>
  b.addEventListener("click", () => {
    segTransporte.querySelectorAll(".seg-btn").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    transporteTipo = b.dataset.transporte;
    labelPlaca.textContent = ETIQUETA_PLACA[transporteTipo];
  })
);

// Limpiamos mientras escribe: mayúsculas, sin separadores y con el tope de 6.
// Así "abc-123" pegado queda "ABC123" y no una placa recortada a medias.
function normalizarPlaca(v) {
  return v.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, MAX_PLACA);
}
inputPlaca.addEventListener("input", () => {
  const limpio = normalizarPlaca(inputPlaca.value);
  if (limpio !== inputPlaca.value) inputPlaca.value = limpio;
});

// ---------- Fotos de las unidades ----------
// Una foto sale de la cámara con 3 MB y el correo se corta en 25 MB, así que
// hay que reducirlas AQUÍ, antes de subirlas. Pasarlas por un canvas además
// les quita los metadatos, incluida la ubicación GPS que traen de fábrica.

// Presupuesto de fotos para todo el conforme, ya reducidas. Con 8 MB el
// correo final ronda los 12 MB y entra con holgura en cualquier buzón.
const PRESUPUESTO_FOTOS = 8 * 1024 * 1024;

// Si el conforme crece, se baja de nivel en vez de pedirle al conductor que
// borre fotos: él nunca debería tener que decidir esto en un patio.
const NIVELES_FOTO = [
  { lado: 1280, calidad: 0.70 },
  { lado: 1024, calidad: 0.70 },
  { lado: 800, calidad: 0.65 },
];
let nivelFoto = 0;

function bytesDeDataUrl(dataUrl) {
  const b64 = dataUrl.slice(dataUrl.indexOf(",") + 1);
  return Math.round((b64.length * 3) / 4);
}

// La orientación de la cámara vive en un dato aparte del archivo. Sin esto,
// la mitad de las fotos saldrían acostadas en el PDF.
async function cargarImagen(archivo) {
  if (window.createImageBitmap) {
    try {
      return await createImageBitmap(archivo, { imageOrientation: "from-image" });
    } catch (e) {
      // Navegador sin soporte: seguimos con el plan B.
    }
  }
  const url = URL.createObjectURL(archivo);
  try {
    return await new Promise((ok, falla) => {
      const img = new Image();
      img.onload = () => ok(img);
      img.onerror = () => falla(new Error("imagen ilegible"));
      img.src = url;
    });
  } finally {
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  }
}

async function reducirFoto(archivo, nivel) {
  const src = await cargarImagen(archivo);
  const escala = Math.min(1, nivel.lado / Math.max(src.width, src.height));
  const lienzo = document.createElement("canvas");
  lienzo.width = Math.round(src.width * escala);
  lienzo.height = Math.round(src.height * escala);
  lienzo.getContext("2d").drawImage(src, 0, 0, lienzo.width, lienzo.height);
  if (src.close) src.close();          // libera el bitmap en el móvil
  return lienzo.toDataURL("image/jpeg", nivel.calidad);
}

function todasLasFotos() {
  return [...cont.querySelectorAll("[data-unidad]")].flatMap((u) => u._fotos || []);
}

function pesoTotalFotos() {
  return todasLasFotos().reduce((suma, f) => suma + f.bytes, 0);
}

function pintarPeso() {
  const caja = document.getElementById("peso-fotos");
  const fotos = todasLasFotos();
  if (!fotos.length) { caja.hidden = true; return; }
  const bytes = pesoTotalFotos();
  // Por debajo de 1 MB, "0,0 MB" no le dice nada a nadie: mejor en KB.
  const peso = bytes < 1024 * 1024
    ? `${Math.round(bytes / 1024)} KB`
    : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  caja.hidden = false;
  caja.textContent = `${fotos.length} ${fotos.length === 1 ? "foto" : "fotos"} · ${peso}`;
  caja.classList.toggle("apretado", pesoTotalFotos() > PRESUPUESTO_FOTOS * 0.75);
}

// Si el conforme se pasa del presupuesto, rehacemos TODAS las fotos en el
// siguiente nivel. Se reprocesa desde el archivo original, no desde la copia
// ya reducida, para no encadenar pérdidas de calidad.
async function reequilibrarFotos() {
  while (pesoTotalFotos() > PRESUPUESTO_FOTOS && nivelFoto < NIVELES_FOTO.length - 1) {
    nivelFoto++;
    for (const foto of todasLasFotos()) {
      foto.dataUrl = await reducirFoto(foto.archivo, NIVELES_FOTO[nivelFoto]);
      foto.bytes = bytesDeDataUrl(foto.dataUrl);
    }
  }
}

function pintarFotos(nodo) {
  const grid = nodo.querySelector("[data-fotos-grid]");
  const fotos = nodo._fotos || [];
  grid.hidden = fotos.length === 0;
  grid.innerHTML = "";
  fotos.forEach((foto, i) => {
    const caja = document.createElement("div");
    caja.className = "foto-item";
    const img = document.createElement("img");
    img.src = foto.dataUrl;
    img.alt = `Foto ${i + 1}`;
    const quitar = document.createElement("button");
    quitar.type = "button";
    quitar.className = "foto-quitar";
    quitar.textContent = "✕";
    quitar.title = "Quitar esta foto";
    quitar.addEventListener("click", () => {
      nodo._fotos.splice(i, 1);
      pintarFotos(nodo);
      pintarPeso();
    });
    caja.append(img, quitar);
    grid.appendChild(caja);
  });
}

function prepararFotos(nodo) {
  nodo._fotos = [];

  nodo.querySelectorAll("[data-foto-input]").forEach((entrada) => {
  const texto = entrada.parentElement.querySelector("[data-foto-texto]");

  entrada.addEventListener("change", async () => {
    const archivos = [...entrada.files];
    entrada.value = "";                 // permite volver a elegir el mismo archivo
    if (!archivos.length) return;

    const original = texto.textContent;
    texto.textContent = "Procesando…";
    try {
      // De a una: decodificar varias fotos grandes a la vez tumba la pestaña
      // en un celular de gama media.
      for (const archivo of archivos) {
        if (!archivo.type.startsWith("image/")) continue;
        const dataUrl = await reducirFoto(archivo, NIVELES_FOTO[nivelFoto]);
        nodo._fotos.push({ archivo, dataUrl, bytes: bytesDeDataUrl(dataUrl) });
        pintarFotos(nodo);
        pintarPeso();
      }
      await reequilibrarFotos();
    } catch (e) {
      mostrarErrores(["No se pudo procesar alguna de las fotos. Intenta de nuevo."]);
    } finally {
      texto.textContent = original;
      pintarFotos(nodo);
      pintarPeso();
    }
  });
  });
}

// ---------- Alto automático de la observación ----------
// Arranca en 3 líneas (el rows="3" de la plantilla manda mientras el alto es
// "auto") y crece con lo que se escriba, para que el conductor vea completo
// lo que anotó sin pelear con una barra de desplazamiento diminuta.
function ajustarAltoObs(ta) {
  if (!ta.offsetParent) return;  // unidad colapsada: no se puede medir
  const est = getComputedStyle(ta);
  const bordes = parseFloat(est.borderTopWidth) + parseFloat(est.borderBottomWidth);
  ta.style.height = "auto";
  ta.style.height = ta.scrollHeight + bordes + "px";
}

function ajustarTodasLasObs() {
  document.querySelectorAll('[data-k="observacion"]').forEach(ajustarAltoObs);
}

// IBM Plex Sans llega por red DESPUÉS del primer render y es más ancha que la
// fuente de reserva: el texto reenvuelve y necesita más líneas de las que
// medimos. Sin este reajuste, la observación queda cortada por abajo.
if (document.fonts) document.fonts.ready.then(ajustarTodasLasObs);
// Al rotar el teléfono cambia el ancho y el texto vuelve a reenvolver.
window.addEventListener("resize", ajustarTodasLasObs);

// ---------- Unidades dinámicas ----------
const cont = document.getElementById("unidades");
const tpl = document.getElementById("tpl-unidad");
const contador = document.getElementById("contador-unidades");

function renumerar() {
  const unidades = [...cont.querySelectorAll("[data-unidad]")];
  unidades.forEach((u, i) => {
    u.querySelector(".unidad-n").textContent = "Unidad " + (i + 1);
  });
  contador.textContent = unidades.length;
}

function resumenUnidad(u) {
  const tipo = u.querySelector(".seg-btn.active").dataset.tipo;
  const val = u.querySelector('[data-k="identificador"]').value.trim().toUpperCase();
  const et = tipo === "vin" ? "VIN" : "Placa";
  u.querySelector(".unidad-resumen").textContent = val ? `${et}: ${val}` : "Sin identificador";
}

function agregarUnidad(enfocar = true) {
  const nodo = tpl.content.firstElementChild.cloneNode(true);

  // Segmento VIN / Placa
  const segBtns = nodo.querySelectorAll(".seg-btn");
  const labelId = nodo.querySelector("[data-label-id]");
  const inputId = nodo.querySelector('[data-k="identificador"]');
  const obs = nodo.querySelector('[data-k="observacion"]');
  obs.addEventListener("input", () => ajustarAltoObs(obs));
  prepararFotos(nodo);
  segBtns.forEach((b) =>
    b.addEventListener("click", () => {
      segBtns.forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      labelId.textContent = b.dataset.tipo === "vin" ? "Número de VIN" : "Número de placa";
      resumenUnidad(nodo);
    })
  );
  inputId.addEventListener("input", () => resumenUnidad(nodo));

  // Colapsar / expandir al tocar el encabezado (menos el botón eliminar)
  nodo.querySelector("[data-toggle]").addEventListener("click", (e) => {
    if (e.target.closest("[data-eliminar]")) return;
    nodo.classList.toggle("colapsada");
    if (!nodo.classList.contains("colapsada")) ajustarAltoObs(obs);
  });

  // Eliminar con confirmación
  nodo.querySelector("[data-eliminar]").addEventListener("click", () => {
    if (confirm("¿Eliminar esta unidad?")) {
      nodo.remove();
      renumerar();
      pintarPeso();
    }
  });

  cont.appendChild(nodo);
  renumerar();
  resumenUnidad(nodo);
  ajustarAltoObs(obs);
  // Solo cuando el conductor la agrega a mano. La primera unidad se crea al
  // cargar la página, y centrarla dejaría el formulario abierto a media
  // altura en vez de arriba.
  if (enfocar) nodo.scrollIntoView({ behavior: "smooth", block: "center" });
}

// El listener recibe el evento como primer argumento; lo envolvemos para que
// no se cuele como "enfocar".
document.getElementById("agregar-unidad").addEventListener("click", () => agregarUnidad());
agregarUnidad(false); // arranca con una unidad, sin mover el scroll

// ---------- Recolección y validación ----------
function leerParte(nombre) {
  const raiz = document.querySelector(`[data-parte="${nombre}"]`);
  const get = (k) => raiz.querySelector(`[data-k="${k}"]`);
  return {
    _els: { nombre: get("nombre"), documento: get("documento"), email: get("email") },
    nombre: get("nombre").value.trim(),
    tipo_documento: get("tipo_documento").value,
    documento: get("documento").value.trim(),
    email: get("email").value.trim(),
    firma: pads[nombre].vacio() ? "" : pads[nombre].dataUrl(),
    firmaVacia: pads[nombre].vacio(),
  };
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function marcar(el, malo) {
  if (!el) return;
  el.classList.toggle("invalid", malo);
}

function validar(payload, partes) {
  const errores = [];

  if (!payload.lugar) {
    errores.push("Indica el lugar de la transferencia.");
    marcar(document.getElementById("lugar"), true);
  } else marcar(document.getElementById("lugar"), false);

  if (!payload.transporte_placa) {
    errores.push("Indica la placa del vehículo que hace el movimiento.");
    marcar(inputPlaca, true);
  } else marcar(inputPlaca, false);

  for (const [rol, p] of Object.entries(partes)) {
    const quien = rol === "entrega" ? "quien entrega" : "quien recibe";
    marcar(p._els.nombre, !p.nombre);
    marcar(p._els.documento, !p.documento);
    const emailMalo = !EMAIL_RE.test(p.email);
    marcar(p._els.email, emailMalo);
    if (!p.nombre) errores.push(`Falta el nombre de ${quien}.`);
    if (!p.documento) errores.push(`Falta el documento de ${quien}.`);
    if (emailMalo) errores.push(`El correo de ${quien} no es válido.`);
  }

  if (payload.unidades.length === 0) {
    errores.push("Agrega al menos una unidad.");
  }
  payload.unidades.forEach((u, i) => {
    if (!u.identificador) errores.push(`La unidad ${i + 1} no tiene identificador.`);
    if (!u.observacion) errores.push(`La unidad ${i + 1} no tiene observaciones.`);
  });

  // Las firmas se revisan de últimas para que la lista de errores siga el
  // mismo orden que el formulario.
  for (const [rol, p] of Object.entries(partes)) {
    const quien = rol === "entrega" ? "quien entrega" : "quien recibe";
    if (p.firmaVacia) errores.push(`Falta la firma de ${quien}.`);
  }

  return errores;
}

function recolectar() {
  const entrega = leerParte("entrega");
  const recibe = leerParte("recibe");
  const unidades = [...cont.querySelectorAll("[data-unidad]")].map((u) => ({
    identificador_tipo: u.querySelector(".seg-btn.active").dataset.tipo,
    identificador: u.querySelector('[data-k="identificador"]').value.trim(),
    observacion: u.querySelector('[data-k="observacion"]').value.trim(),
    fotos: (u._fotos || []).map((f) => f.dataUrl),
  }));
  const payload = {
    lugar: document.getElementById("lugar").value.trim(),
    transporte_tipo: transporteTipo,
    transporte_placa: normalizarPlaca(inputPlaca.value),
    entrega: strip(entrega),
    recibe: strip(recibe),
    unidades,
  };
  return { payload, partes: { entrega, recibe } };
}
function strip(p) {
  return { nombre: p.nombre, tipo_documento: p.tipo_documento,
           documento: p.documento, email: p.email, firma: p.firma };
}

// ---------- Envío ----------
const errorBox = document.getElementById("error-box");
const btnEnviar = document.getElementById("enviar");

function mostrarErrores(lista) {
  errorBox.innerHTML = "<strong>Revisa lo siguiente:</strong><br>" + lista.join("<br>");
  errorBox.hidden = false;
  errorBox.scrollIntoView({ behavior: "smooth", block: "center" });
}

btnEnviar.addEventListener("click", async () => {
  errorBox.hidden = true;
  const { payload, partes } = recolectar();
  const errores = validar(payload, partes);
  if (errores.length) { mostrarErrores(errores); return; }

  btnEnviar.disabled = true;
  btnEnviar.textContent = "Enviando…";
  try {
    const res = await fetch("/api/acta", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!data.ok) {
      mostrarErrores([data.error || "No se pudo procesar el conforme."]);
      return;
    }
    mostrarExito(data);
  } catch (e) {
    mostrarErrores(["Sin conexión con el servidor. Intenta de nuevo."]);
  } finally {
    btnEnviar.disabled = false;
    btnEnviar.textContent = "Enviar conforme";
  }
});

// ---------- Pantalla de éxito ----------
let ultimoPdf = null;
let ultimoNombre = "conforme.pdf";

function mostrarExito(data) {
  ultimoPdf = data.pdf_base64;
  ultimoNombre = data.filename || "conforme.pdf";
  document.getElementById("exito-folio").textContent = data.folio;
  const detalle = document.getElementById("exito-detalle");
  if (data.email_ok) {
    detalle.textContent = "El documento se envió al gerente y a los correos de quien entrega y recibe.";
    detalle.classList.remove("warn");
  } else {
    detalle.textContent = (data.email_error || "No se pudo enviar el correo.") +
      " Descarga el PDF como respaldo.";
    detalle.classList.add("warn");
  }
  document.getElementById("vista-form").hidden = true;
  document.getElementById("barra-accion").hidden = true;
  document.getElementById("vista-exito").hidden = false;
  window.scrollTo(0, 0);
}

document.getElementById("descargar").addEventListener("click", () => {
  if (!ultimoPdf) return;
  const bytes = Uint8Array.from(atob(ultimoPdf), (c) => c.charCodeAt(0));
  const blob = new Blob([bytes], { type: "application/pdf" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = ultimoNombre; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
});

document.getElementById("nueva-acta").addEventListener("click", () => {
  location.reload();
});
