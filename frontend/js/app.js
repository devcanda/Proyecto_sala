/**
 * app.js
 * -------
 * Orquestador principal del frontend. Responsabilidades:
 *  - Decidir que vista mostrar (retail vs hospitalidad) segun el modo
 *    elegido en la barra superior (persistido en localStorage).
 *  - Cargar el fragmento HTML correspondiente (views/*.html) dentro de
 *    #app-view.
 *  - Mantener el estado de la orden/cuenta en curso y sincronizarlo con
 *    el backend a traves de api.js.
 *  - Reaccionar a los escaneos de codigo de barras (evento
 *    "barcode:scan" emitido por barcode.js).
 *
 * Nota: se usa fetch() para cargar los fragmentos de views/, lo cual
 * requiere servir el frontend por http (ej. `npx http-server frontend`,
 * o el dev-server que provea Tauri/Electron) en vez de abrir index.html
 * directamente como archivo local (file://), ya que la mayoria de
 * navegadores bloquean fetch() sobre ese protocolo.
 */
const state = {
  modo: localStorage.getItem("salsa_pos_modo") || "retail",
  productos: [],
  ordenActual: null, // { id, tipo_orden, mesa_id, detalles, estado, ... }
  mesaActual: null,
};

const connectionStatusEl = document.getElementById("connection-status");
const appViewEl = document.getElementById("app-view");

// ---------- Arranque ----------

async function init() {
  marcarModoActivo();
  await verificarConexion();

  try {
    state.productos = await api.listarProductos();
  } catch (err) {
    console.error("No se pudieron cargar los productos:", err);
    state.productos = [];
  }

  document.querySelectorAll(".modo-btn").forEach((btn) => {
    btn.addEventListener("click", () => cambiarModo(btn.dataset.modo));
  });

  document.addEventListener("barcode:scan", (e) => onBarcodeScan(e.detail));

  await renderVistaActual();
}

async function verificarConexion() {
  try {
    await api.salud();
    connectionStatusEl.textContent = "● backend conectado";
    connectionStatusEl.className = "topbar__status ok";
  } catch (err) {
    connectionStatusEl.textContent = "● sin conexion con el backend";
    connectionStatusEl.className = "topbar__status error";
  }
}

function marcarModoActivo() {
  document.querySelectorAll(".modo-btn").forEach((btn) => {
    btn.classList.toggle("activo", btn.dataset.modo === state.modo);
  });
}

function cambiarModo(modo) {
  if (modo === state.modo) return;
  state.modo = modo;
  state.ordenActual = null;
  state.mesaActual = null;
  localStorage.setItem("salsa_pos_modo", modo);
  marcarModoActivo();
  renderVistaActual();
}

// ---------- Ruteo de vistas ----------

async function renderVistaActual() {
  const archivo = state.modo === "hospitalidad" ? "pos_hospitalidad.html" : "pos_retail.html";
  const html = await fetch(`views/${archivo}`).then((r) => r.text());
  appViewEl.innerHTML = html;

  if (state.modo === "hospitalidad") {
    await renderMesasGrid();
    document.getElementById("btn-volver-mesas").addEventListener("click", volverAMesas);
  } else {
    renderProductosGrid();
  }

  const btnCobrar = document.getElementById("btn-cobrar");
  if (btnCobrar) btnCobrar.addEventListener("click", cobrarOrdenActual);
}

// ---------- Modo Retail ----------

function renderProductosGrid() {
  const grid = document.getElementById("productos-grid");
  if (!grid) return;
  grid.innerHTML = "";

  state.productos.forEach((producto) => {
    const card = document.createElement("div");
    card.className = "producto-card";
    card.innerHTML = `<strong>${producto.nombre}</strong><br/>$${Number(producto.precio_venta).toFixed(2)}`;
    card.addEventListener("click", () => agregarItem(producto, 1));
    grid.appendChild(card);
  });
}

// ---------- Modo Hospitalidad ----------

async function renderMesasGrid() {
  const grid = document.getElementById("mesas-grid");
  let mesas = [];
  try {
    mesas = await api.listarMesas();
  } catch (err) {
    console.error("No se pudieron cargar las mesas:", err);
  }

  grid.innerHTML = "";
  mesas.forEach((mesa) => {
    const card = document.createElement("div");
    card.className = `mesa-card ${mesa.estado}`;
    card.textContent = mesa.nombre;
    card.addEventListener("click", () => seleccionarMesa(mesa));
    grid.appendChild(card);
  });
}

async function seleccionarMesa(mesa) {
  state.mesaActual = mesa;

  // Si la mesa ya tenia una cuenta abierta, se retoma; si no, se crea al
  // agregar el primer item (ver asegurarOrdenActual).
  try {
    state.ordenActual = await api.ordenAbiertaDeMesa(mesa.id);
  } catch (err) {
    state.ordenActual = null;
  }

  document.getElementById("vista-mesas").hidden = true;
  document.getElementById("vista-cuenta").hidden = false;
  document.getElementById("cuenta-titulo").textContent = mesa.nombre;

  renderProductosGrid();
  actualizarTicket();
}

function volverAMesas() {
  state.mesaActual = null;
  document.getElementById("vista-mesas").hidden = false;
  document.getElementById("vista-cuenta").hidden = true;
  renderMesasGrid();
}

// ---------- Logica compartida de orden/ticket ----------

async function asegurarOrdenActual() {
  if (state.ordenActual) return state.ordenActual;

  const payload =
    state.modo === "hospitalidad"
      ? { tipo_orden: "mesa", mesa_id: state.mesaActual.id, detalles: [] }
      : { tipo_orden: "directa", detalles: [] };

  state.ordenActual = await api.crearOrden(payload);
  return state.ordenActual;
}

async function agregarItem(producto, cantidad) {
  try {
    await asegurarOrdenActual();
    state.ordenActual = await api.agregarDetalle(state.ordenActual.id, {
      producto_id: producto.id,
      cantidad,
    });
    actualizarTicket();
  } catch (err) {
    alert(`No se pudo agregar el producto: ${err.message}`);
  }
}

async function onBarcodeScan({ codigo, cantidad }) {
  try {
    const producto = await api.buscarProductoPorCodigo(codigo);
    await agregarItem(producto, cantidad);
  } catch (err) {
    alert(`Codigo no reconocido: ${codigo}`);
  }
}

function actualizarTicket() {
  const lineasEl = document.getElementById("ticket-lineas");
  const totalEl = document.getElementById("ticket-total");
  const btnCobrar = document.getElementById("btn-cobrar");
  if (!lineasEl) return;

  const detalles = state.ordenActual?.detalles || [];
  lineasEl.innerHTML = "";
  let total = 0;

  detalles.forEach((linea) => {
    const producto = state.productos.find((p) => p.id === linea.producto_id);
    const subtotal = Number(linea.cantidad) * Number(linea.precio_unitario_historico);
    total += subtotal;

    const li = document.createElement("li");
    li.className = "ticket-linea";
    li.innerHTML = `<span>${linea.cantidad} x ${producto ? producto.nombre : "#" + linea.producto_id}</span><span>$${subtotal.toFixed(2)}</span>`;
    lineasEl.appendChild(li);
  });

  totalEl.textContent = `$${total.toFixed(2)}`;
  if (btnCobrar) btnCobrar.disabled = detalles.length === 0;
}

async function cobrarOrdenActual() {
  if (!state.ordenActual) return;
  try {
    await api.pagarOrden(state.ordenActual.id);
    state.ordenActual = null;
    if (state.modo === "hospitalidad") {
      volverAMesas();
    } else {
      actualizarTicket();
    }
  } catch (err) {
    alert(`No se pudo cobrar la orden: ${err.message}`);
  }
}

init();
