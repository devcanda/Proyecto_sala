/**
 * app.js
 * -------
 * Orquestador principal del frontend. Responsabilidades:
 *  - Decidir que "seccion" de nivel superior mostrar (venta / productos /
 *    inventario / alertas), elegida desde la barra lateral.
 *  - Dentro de la seccion "venta", decidir el sub-modo (retail vs
 *    hospitalidad), persistido en localStorage como antes.
 *  - Cargar el fragmento HTML correspondiente (views/*.html) dentro de
 *    #app-view.
 *  - Mantener el estado de la orden/cuenta en curso y sincronizarlo con
 *    el backend a traves de api.js.
 *  - Reaccionar a los escaneos de codigo de barras (evento
 *    "barcode:scan" emitido por barcode.js), solo relevante en "venta".
 *
 * Nota: se usa fetch() para cargar los fragmentos de views/, lo cual
 * requiere servir el frontend por http (ej. `npx http-server frontend`,
 * o el dev-server que provea Tauri/Electron) en vez de abrir index.html
 * directamente como archivo local (file://), ya que la mayoria de
 * navegadores bloquean fetch() sobre ese protocolo.
 */
const state = {
  seccion: "venta",
  modo: localStorage.getItem("salsa_pos_modo") || "retail",
  productos: [],
  impresoras: [],
  ordenActual: null, // { id, tipo_orden, mesa_id, detalles, estado, ... }
  mesaActual: null,
  inventarioProductoId: null,
  filtroCategoria: "todas", // solo se usa en la grilla de Retail
  adminSubmenuAbierto: false, // Productos/Inventario/Alertas/Configuracion
};

const SECCIONES_ADMIN = ["productos", "inventario", "alertas", "configuracion"];

const connectionStatusEl = document.getElementById("connection-status");
const appViewEl = document.getElementById("app-view");

// ---------- Formato numerico (punto de miles, coma decimal) ----------
// Convencion pedida por el negocio: 1.234,56 en vez de 1234.56. Los
// <input type="number"> de los formularios NO pasan por aqui: el
// navegador los maneja siempre con punto decimal, sin separador de
// miles, sin importar el idioma/config regional (limitacion del propio
// tipo de input, no de esta app) - esta funcion solo aplica a lo que se
// MUESTRA (grillas, tickets, tablas), nunca a lo que se tipea.

function formatearNumero(valor, decimales) {
  const num = Number(valor) || 0;
  // Recorta ceros de mas al final (ej. cantidad "1.000" -> "1", "0.350" -> "0.35")
  const texto = num.toFixed(decimales).replace(/\.?0+$/, "");
  const [entero, decimal] = texto.split(".");
  const enteroConPuntos = entero.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return decimal ? `${enteroConPuntos},${decimal}` : enteroConPuntos;
}

// Precios/totales: siempre 2 decimales fijos (ej. "$1.234,50", no "$1.234,5").
function formatearMoneda(valor) {
  const num = Number(valor) || 0;
  const partes = num.toFixed(2).split(".");
  const enteroConPuntos = partes[0].replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return `$${enteroConPuntos},${partes[1]}`;
}

// Para campos de entrada tipo "text" (.input-precio): "1.234,50"
function formatearInputMoneda(valor) {
  if (valor === "" || valor === null || valor === undefined) return "";
  const num = Number(valor);
  if (isNaN(num)) return "";
  const partes = num.toFixed(2).split(".");
  const enteroConPuntos = partes[0].replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return `${enteroConPuntos},${partes[1]}`;
}

// A la inversa: "1.234,50" -> 1234.50 (float) para enviar a backend o calcular
function parsearMoneda(texto) {
  if (!texto) return 0;
  let normalizado = String(texto).replace(/\./g, ""); // quitar puntos de miles
  normalizado = normalizado.replace(",", "."); // convertir coma decimal a punto
  return Number(normalizado) || 0;
}

// Cantidades (unidades, gramos, etc.): hasta 3 decimales, sin ceros de
// relleno, para que "1" siga viendose como "1" y no como "1,000".
function formatearCantidad(valor) {
  return formatearNumero(valor, 3);
}

const ETIQUETAS_UNIDAD_MEDIDA = {
  unidad: "Unidad",
  kg: "Kg",
  gramo: "Gramo",
  litro: "Litro",
  mililitro: "Mililitro",
  libra: "Libra",
};
function etiquetaUnidadMedida(valor) {
  return ETIQUETAS_UNIDAD_MEDIDA[valor] || valor || "";
}

// ---------- Notificaciones no bloqueantes ----------

let toastTimeoutId = null;
function mostrarToast(mensaje, tipo = "exito") {
  const toast = document.getElementById("toast");
  if (!toast) return;
  toast.textContent = mensaje;
  toast.className = tipo === "error" ? "toast error" : "toast";
  toast.hidden = false;
  clearTimeout(toastTimeoutId);
  toastTimeoutId = setTimeout(() => {
    toast.hidden = true;
  }, 3000);
}

// ---------- Arranque ----------

async function init() {
  document.addEventListener("blur", (e) => {
    if (e.target && e.target.classList.contains("input-precio")) {
      const valStr = e.target.value.trim();
      if (valStr !== "") {
        const parsed = parsearMoneda(valStr);
        e.target.value = formatearInputMoneda(parsed);
        e.target.dispatchEvent(new Event("input")); // Para forzar calculo de margen si aplica
      }
    }
  }, true);

  await verificarConexion();

  try {
    state.productos = await api.listarProductos();
  } catch (err) {
    console.error("No se pudieron cargar los productos:", err);
    state.productos = [];
  }

  document.querySelectorAll(".seccion-btn[data-seccion]").forEach((btn) => {
    btn.addEventListener("click", () => cambiarSeccion(btn.dataset.seccion));
  });
  document.getElementById("btn-admin-toggle").addEventListener("click", toggleAdminSubmenu);

  // Cerrar el menu flotante al pulsar fuera o con Escape, como cualquier
  // menu contextual de escritorio.
  document.addEventListener("click", (e) => {
    if (!state.adminSubmenuAbierto) return;
    const menu = document.getElementById("admin-submenu");
    const toggle = document.getElementById("btn-admin-toggle");
    if (menu.contains(e.target) || toggle.contains(e.target)) return;
    cerrarAdminSubmenu();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") cerrarAdminSubmenu();
  });
  document.querySelectorAll(".modo-btn").forEach((btn) => {
    btn.addEventListener("click", () => cambiarModo(btn.dataset.modo));
  });

  document.addEventListener("barcode:scan", (e) => onBarcodeScan(e.detail));

  await renderSeccionActual();
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

// ---------- Ruteo de secciones de nivel superior ----------

function marcarSeccionActiva() {
  document.querySelectorAll(".seccion-btn[data-seccion]").forEach((btn) => {
    btn.classList.toggle("activo", btn.dataset.seccion === state.seccion);
  });

  // Deja la seccion actual en el <body> para que el CSS pueda reaccionar a
  // ella sin consultar este estado. Se usa para ocultar la barra lateral en
  // Venta: la pantalla de caja de Aronium es a pantalla completa, y la
  // entrada a Administracion pasa a ser el boton de los tres puntos
  // (ver el comentario de navegacion en index.html).
  document.body.dataset.seccion = state.seccion;

  const esAdmin = SECCIONES_ADMIN.includes(state.seccion);
  // El menu de los tres puntos es un desplegable de verdad: lo abre y lo
  // cierra el usuario. Antes se forzaba abierto mientras se estuviera en
  // una seccion de administracion, que era lo correcto cuando era un
  // submenu fijo dentro de la barra lateral, pero como menu flotante lo
  // dejaria pegado en pantalla tapando el contenido.
  const abierto = state.adminSubmenuAbierto;
  document.getElementById("admin-submenu").hidden = !abierto;

  const toggle = document.getElementById("btn-admin-toggle");
  toggle.classList.toggle("activo", esAdmin || abierto);
  toggle.setAttribute("aria-expanded", abierto ? "true" : "false");
}

function toggleAdminSubmenu() {
  state.adminSubmenuAbierto = !state.adminSubmenuAbierto;
  marcarSeccionActiva();
}

function cerrarAdminSubmenu() {
  if (!state.adminSubmenuAbierto) return;
  state.adminSubmenuAbierto = false;
  marcarSeccionActiva();
}

function cambiarSeccion(seccion) {
  // Cerrar antes del corto-circuito: elegir la seccion en la que ya se
  // esta tiene que cerrar el menu igual.
  cerrarAdminSubmenu();
  if (seccion === state.seccion) return;
  state.seccion = seccion;
  renderSeccionActual();
}

async function renderSeccionActual() {
  marcarSeccionActiva();
  document.getElementById("venta-subnav").hidden = state.seccion !== "venta";

  if (state.seccion === "productos") return renderSeccionProductos();
  if (state.seccion === "inventario") return renderSeccionInventario();
  if (state.seccion === "alertas") return renderSeccionAlertas();
  if (state.seccion === "configuracion") return renderSeccionConfiguracion();
  return renderVistaVenta();
}

// ---------- Seccion Venta (retail / hospitalidad) ----------

function marcarModoActivo() {
  document.querySelectorAll(".modo-btn").forEach((btn) => {
    btn.classList.toggle("activo", btn.dataset.modo === state.modo);
  });
}

function cambiarModo(modo) {
  cerrarAdminSubmenu();
  if (modo === state.modo) return;
  state.modo = modo;
  state.ordenActual = null;
  state.mesaActual = null;
  localStorage.setItem("salsa_pos_modo", modo);
  marcarModoActivo();
  renderVistaVenta();
}

async function renderVistaVenta() {
  marcarModoActivo();
  const archivo = state.modo === "hospitalidad" ? "pos_hospitalidad.html" : "pos_retail.html";
  const html = await fetch(`views/${archivo}`).then((r) => r.text());
  appViewEl.innerHTML = html;

  if (state.modo === "hospitalidad") {
    await renderMesasGrid();
    document.getElementById("btn-volver-mesas").addEventListener("click", volverAMesas);
  } else {
    renderCategoriasTabs();
    renderProductosGrid();
    actualizarTicket();
  }

  // Fuera de la rama de Retail: desde el 2026-09-08 Hospitalidad tambien
  // trae este buscador (es el campo donde escribe el lector de codigo de
  // barras), asi que el filtrado hay que enlazarlo en los dos modos.
  const buscador = document.getElementById("productos-buscador");
  if (buscador) buscador.addEventListener("input", () => renderProductosGrid());

  const btnCobrar = document.getElementById("btn-cobrar");
  if (btnCobrar) btnCobrar.addEventListener("click", cobrarOrdenActual);
}

// Buscador y pestañas de categoria: solo existen en views/pos_retail.html.
// Cuando se llama desde Hospitalidad (mismo #productos-grid reutilizado en
// la cuenta de una mesa), esos elementos no existen y se muestra el
// catalogo completo sin filtrar, tal como antes.

function categoriasDisponibles() {
  const set = new Set();
  state.productos.forEach((p) => {
    if (p.grupo) set.add(p.grupo);
  });
  return Array.from(set).sort();
}

function renderCategoriasTabs() {
  const cont = document.getElementById("categorias-tabs");
  if (!cont) return;
  cont.innerHTML = "";

  const categorias = ["todas", ...categoriasDisponibles()];
  categorias.forEach((cat) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "categoria-tab";
    btn.textContent = cat === "todas" ? "Todas" : cat;
    btn.classList.toggle("activo", state.filtroCategoria === cat);
    btn.addEventListener("click", () => {
      state.filtroCategoria = cat;
      renderCategoriasTabs();
      renderProductosGrid();
    });
    cont.appendChild(btn);
  });
}

function productosFiltrados() {
  const buscadorEl = document.getElementById("productos-buscador");
  const termino = buscadorEl ? buscadorEl.value.trim().toLowerCase() : "";

  // El filtro por categoria solo vale donde hay pestañas para cambiarlo.
  // En la cuenta de Hospitalidad no las hay, y sin esta guarda arrastraria
  // la categoria que quedo elegida en Retail, escondiendo productos sin
  // que se pueda deshacer desde esa pantalla.
  const conCategorias = !!document.getElementById("categorias-tabs");

  return state.productos.filter((p) => {
    if (conCategorias && state.filtroCategoria !== "todas" && p.grupo !== state.filtroCategoria) return false;
    if (termino) {
      const enNombre = p.nombre.toLowerCase().includes(termino);
      const enCodigo = (p.codigo_barras || "").toLowerCase().includes(termino);
      if (!enNombre && !enCodigo) return false;
    }
    return true;
  });
}

function renderProductosGrid() {
  const grid = document.getElementById("productos-grid");
  if (!grid) return;
  grid.innerHTML = "";

  // El filtro solo aplica cuando la vista trae el buscador (Retail); la
  // cuenta de una mesa en Hospitalidad reutiliza esta funcion pero sin
  // esos controles, y siempre muestra el catalogo completo.
  const conFiltros = !!document.getElementById("productos-buscador");
  const lista = conFiltros ? productosFiltrados() : state.productos;

  lista.forEach((producto) => {
    const card = document.createElement("div");
    card.className = "producto-card";
    card.innerHTML = `<strong>${producto.nombre}</strong><br/>${formatearMoneda(producto.precio_venta)}`;
    card.addEventListener("click", () => agregarItem(producto, 1));
    grid.appendChild(card);
  });
}

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

  const nuevaCard = document.createElement("div");
  nuevaCard.className = "mesa-card mesa-nueva";
  nuevaCard.textContent = "+ Nueva mesa";
  nuevaCard.addEventListener("click", () => {
    document.getElementById("form-nueva-mesa").hidden = false;
  });
  grid.appendChild(nuevaCard);

  const form = document.getElementById("form-nueva-mesa");
  form.hidden = true;
  form.onsubmit = async (e) => {
    e.preventDefault();
    const nombre = document.getElementById("nueva-mesa-nombre").value;
    const capacidadRaw = document.getElementById("nueva-mesa-capacidad").value;
    try {
      await api.crearMesa({ nombre, capacidad: capacidadRaw ? Number(capacidadRaw) : null });
      form.reset();
      await renderMesasGrid();
    } catch (err) {
      alert(`No se pudo crear la mesa: ${err.message}`);
    }
  };
  document.getElementById("btn-cancelar-nueva-mesa").onclick = () => {
    form.reset();
    form.hidden = true;
  };
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

/**
 * Enter en el campo de captura (ver frontend/js/barcode.js).
 *
 * Desde el 2026-09-08 ese campo es el MISMO buscador de la pantalla, asi
 * que un Enter puede venir de dos sitios muy distintos: del lector, que
 * teclea un codigo exacto, o de una persona que estaba buscando por
 * nombre. Por eso se intenta primero el codigo exacto y solo despues se
 * interpreta como busqueda.
 */
async function onBarcodeScan({ codigo, cantidad }) {
  if (state.seccion !== "venta") return;

  const termino = codigo.trim().toLowerCase();

  // 1. Coincidencia exacta de codigo contra el catalogo ya cargado. Es el
  //    caso del lector fisico, y se resuelve sin salir a la red.
  const porCodigo = state.productos.find(
    (p) =>
      (p.codigo_barras || "").toLowerCase() === termino ||
      (p.codigo || "").toLowerCase() === termino
  );
  if (porCodigo) {
    await agregarItem(porCodigo, cantidad);
    window.barcodeFocus.limpiar();
    return;
  }

  // 2. Busqueda por nombre: si el filtro dejo un unico producto a la vista
  //    no hay ambiguedad. Va ANTES de preguntarle al backend para que
  //    teclear un nombre no dispare una peticion condenada al 404 (que
  //    ademas ensucia la consola en el uso normal). No puede confundirse
  //    con un escaneo: si el codigo leido no esta en el catalogo, el filtro
  //    no deja ningun producto a la vista y este caso no se cumple.
  const visibles = productosFiltrados();
  if (visibles.length === 1) {
    await agregarItem(visibles[0], cantidad);
    window.barcodeFocus.limpiar();
    return;
  }

  // 3. Ultimo recurso, contra el backend. Cubre un codigo que exista en la
  //    base pero no en el catalogo cargado en memoria: por ejemplo, un
  //    producto dado de alta desde otra caja en modo Red LAN.
  try {
    const producto = await api.buscarProductoPorCodigo(codigo);
    await agregarItem(producto, cantidad);
    window.barcodeFocus.limpiar();
    return;
  } catch (err) {
    /* No existe. Se avisa abajo. */
  }

  // 4. Con varios candidatos no se adivina: el operario sigue afinando la
  //    busqueda y la grilla ya le esta mostrando las opciones. Solo se
  //    avisa cuando no queda ninguna, y con un toast en vez del alert()
  //    bloqueante de antes, que ahora saltaria ante cualquier busqueda sin
  //    resultados y habria que descartarlo a mano.
  if (visibles.length === 0) {
    mostrarToast(`Codigo no reconocido: ${codigo}`, "error");
  }
}

function actualizarTicket() {
  const lineasEl = document.getElementById("ticket-lineas");
  const vacioEl = document.getElementById("ticket-vacio");
  const totalEl = document.getElementById("ticket-total");
  const btnCobrar = document.getElementById("btn-cobrar");
  if (!lineasEl) return;

  const detalles = state.ordenActual?.detalles || [];
  lineasEl.innerHTML = "";
  let total = 0;

  detalles.forEach((linea) => {
    const producto = state.productos.find((p) => p.id === linea.producto_id);
    const precio = Number(linea.precio_unitario_historico);
    const cantidad = Number(linea.cantidad);
    const subtotal = cantidad * precio;
    total += subtotal;

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${producto ? producto.nombre : "#" + linea.producto_id}</td>
      <td>${formatearCantidad(cantidad)}</td>
      <td>${formatearMoneda(precio)}</td>
      <td>${formatearMoneda(subtotal)}</td>
    `;
    lineasEl.appendChild(tr);
  });

  if (vacioEl) vacioEl.hidden = detalles.length > 0;
  totalEl.textContent = formatearMoneda(total);
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

// ---------- Seccion Productos ----------

async function refrescarProductos() {
  state.productos = await api.listarProductos();
}

async function renderSeccionProductos() {
  const html = await fetch("views/productos.html").then((r) => r.text());
  appViewEl.innerHTML = html;

  await refrescarProductos();
  poblarTablaProductos();
  await refrescarImpresoras();
  poblarSelectImpresoras();
  await poblarSelectProveedores();

  document.getElementById("form-producto").addEventListener("submit", onSubmitProducto);
  document.getElementById("btn-cancelar-edicion").addEventListener("click", cancelarEdicionProducto);
  document.getElementById("btn-generar-codigo-barras").addEventListener("click", generarCodigoBarras);
  document.getElementById("producto-costo").addEventListener("input", calcularMargen);
  document.getElementById("producto-precio").addEventListener("input", calcularMargen);
  document.getElementById("producto-stock-bajo-activo").addEventListener("change", actualizarCampoStockBajo);
  document.getElementById("producto-imagen-input").addEventListener("change", manejarSeleccionImagen);

  actualizarVisibilidadCantidadInicial(true); // el formulario arranca en modo "Nuevo producto"
}

function poblarTablaProductos() {
  const body = document.getElementById("productos-tabla-body");
  if (!body) return;
  body.innerHTML = "";

  state.productos.forEach((producto) => {
    const tr = document.createElement("tr");
    tr.className = "fila-clickable";
    tr.innerHTML = `
      <td>${producto.nombre}</td>
      <td>${producto.tipo}</td>
      <td>${formatearMoneda(producto.precio_venta)}</td>
      <td>${producto.grupo || ""}</td>
      <td>${producto.codigo_barras || ""}</td>
    `;
    tr.addEventListener("click", () => cargarProductoEnFormulario(producto));
    body.appendChild(tr);
  });

  const datalist = document.getElementById("grupos-existentes");
  if (datalist) {
    datalist.innerHTML = "";
    categoriasDisponibles().forEach((cat) => {
      const opt = document.createElement("option");
      opt.value = cat;
      datalist.appendChild(opt);
    });
  }
}

// ---------- Interruptores / campos condicionales ----------

function actualizarCampoStockBajo() {
  const activo = document.getElementById("producto-stock-bajo-activo").checked;
  document.getElementById("campo-stock-bajo-umbral").hidden = !activo;
}

// La cantidad inicial (que registra el primer lote) solo tiene sentido al
// crear un producto nuevo; una vez tiene id, los ingresos de mercaderia
// se gestionan desde la seccion Inventario para no duplicar caminos.
function actualizarVisibilidadCantidadInicial(mostrar) {
  document.querySelectorAll(".campo-solo-creacion").forEach((el) => {
    el.hidden = !mostrar;
  });
}

// "Margen de ganancia" = cuanto se gana sobre el costo (markup), no sobre
// el precio de venta: margen% = (precio - costo) / costo * 100. Es de
// solo lectura, siempre recalculado desde costo+precio (no se guarda en
// la base de datos).
function calcularMargen() {
  const costo = parsearMoneda(document.getElementById("producto-costo").value);
  const precio = parsearMoneda(document.getElementById("producto-precio").value);
  const campoMargen = document.getElementById("producto-margen");
  if (!costo || costo <= 0 || !precio) {
    campoMargen.value = "--";
    return;
  }
  const margen = ((precio - costo) / costo) * 100;
  campoMargen.value = `${formatearNumero(margen, 2)}%`;
}

// Genera un EAN-13 valido (12 digitos aleatorios + digito verificador
// calculado), para el boton "Generar" cuando el producto no tiene codigo
// de barras propio y el negocio quiere imprimirle uno.
function generarCodigoBarras() {
  let cuerpo = "";
  for (let i = 0; i < 12; i++) cuerpo += Math.floor(Math.random() * 10);

  let suma = 0;
  for (let i = 0; i < 12; i++) {
    const digito = Number(cuerpo[i]);
    suma += i % 2 === 0 ? digito : digito * 3;
  }
  const verificador = (10 - (suma % 10)) % 10;

  document.getElementById("producto-codigo-barras").value = cuerpo + verificador;
}

// ---------- Imagen del producto ----------

async function manejarSeleccionImagen(e) {
  const archivo = e.target.files[0];
  if (!archivo) return;

  const id = document.getElementById("producto-id").value;
  if (!id) {
    alert("Guarda el producto primero (boton Guardar) para poder subirle una imagen.");
    e.target.value = "";
    return;
  }

  try {
    const producto = await api.subirImagenProducto(id, archivo);
    mostrarPreviewImagen(producto.imagen);
    await refrescarProductos();
    poblarTablaProductos();
  } catch (err) {
    alert(`No se pudo subir la imagen: ${err.message}`);
  }
}

function mostrarPreviewImagen(nombreArchivo) {
  const img = document.getElementById("producto-imagen-preview");
  if (!nombreArchivo) {
    img.hidden = true;
    img.removeAttribute("src");
    return;
  }
  // Cache-bust: si se reemplaza la imagen del mismo producto, el nombre
  // de archivo no cambia (siempre "{id}.jpg"), asi que sin esto el
  // navegador podria seguir mostrando la version vieja desde cache.
  img.src = `${api.urlImagen(nombreArchivo)}?t=${Date.now()}`;
  img.hidden = false;
}

// ---------- Formulario: cargar / cancelar / guardar ----------

function cargarProductoEnFormulario(producto) {
  document.getElementById("producto-id").value = producto.id;
  document.getElementById("producto-nombre").value = producto.nombre;
  document.getElementById("producto-codigo").value = producto.codigo || "";
  document.getElementById("producto-codigo-barras").value = producto.codigo_barras || "";
  document.getElementById("producto-unidad-medida").value = producto.unidad_medida || "unidad";
  document.getElementById("producto-grupo").value = producto.grupo || "";
  document.getElementById("producto-tipo").value = producto.tipo;
  document.getElementById("producto-costo").value = formatearInputMoneda(producto.costo);
  document.getElementById("producto-precio").value = formatearInputMoneda(producto.precio_venta);
  document.getElementById("producto-incluye-impuesto").checked = !!producto.incluye_impuesto;
  document.getElementById("producto-proveedor").value = producto.proveedor_id || "";
  document.getElementById("producto-impresora").value = producto.impresora_destino || "";
  document.getElementById("producto-activo").checked = producto.activo !== false;
  document.getElementById("producto-es-servicio").checked = !!producto.es_servicio;
  document.getElementById("producto-stock-bajo-activo").checked = !!producto.stock_bajo_activo;
  document.getElementById("producto-stock-bajo-umbral").value = producto.stock_bajo_umbral || "";
  document.getElementById("producto-descripcion").value = producto.descripcion || "";
  document.getElementById("productos-form-titulo").textContent = `Editar: ${producto.nombre}`;
  document.getElementById("btn-cancelar-edicion").hidden = false;

  calcularMargen();
  actualizarCampoStockBajo();
  actualizarVisibilidadCantidadInicial(false); // ya tiene id: los ingresos van por Inventario
  mostrarPreviewImagen(producto.imagen);

  actualizarPanelReceta(producto);
  actualizarPanelNotas(producto);
}

function cancelarEdicionProducto() {
  document.getElementById("form-producto").reset();
  document.getElementById("producto-id").value = "";
  document.getElementById("productos-form-titulo").textContent = "Nuevo producto";
  document.getElementById("btn-cancelar-edicion").hidden = true;
  document.getElementById("panel-receta").hidden = true;
  document.getElementById("panel-notas").hidden = true;
  document.getElementById("campo-stock-bajo-umbral").hidden = true;
  document.getElementById("producto-margen").value = "";
  actualizarVisibilidadCantidadInicial(true);
  mostrarPreviewImagen(null);
}

async function onSubmitProducto(e) {
  e.preventDefault();
  const id = document.getElementById("producto-id").value;
  const proveedorId = document.getElementById("producto-proveedor").value;
  const stockBajoActivo = document.getElementById("producto-stock-bajo-activo").checked;

  const payload = {
    nombre: document.getElementById("producto-nombre").value,
    codigo: document.getElementById("producto-codigo").value || null,
    codigo_barras: document.getElementById("producto-codigo-barras").value || null,
    unidad_medida: document.getElementById("producto-unidad-medida").value,
    tipo: document.getElementById("producto-tipo").value,
    costo: parsearMoneda(document.getElementById("producto-costo").value) || null,
    precio_venta: parsearMoneda(document.getElementById("producto-precio").value),
    incluye_impuesto: document.getElementById("producto-incluye-impuesto").checked,
    grupo: document.getElementById("producto-grupo").value || null,
    descripcion: document.getElementById("producto-descripcion").value || null,
    es_servicio: document.getElementById("producto-es-servicio").checked,
    proveedor_id: proveedorId ? Number(proveedorId) : null,
    stock_bajo_activo: stockBajoActivo,
    stock_bajo_umbral: stockBajoActivo
      ? document.getElementById("producto-stock-bajo-umbral").value || null
      : null,
    impresora_destino: document.getElementById("producto-impresora").value || null,
    activo: document.getElementById("producto-activo").checked,
  };

  let toastMensaje = "Producto guardado correctamente.";
  let toastTipo = "exito";

  try {
    const producto = id ? await api.editarProducto(id, payload) : await api.crearProducto(payload);

    // La cantidad inicial solo aplica al CREAR (nunca al editar, para no
    // registrar un lote de mas cada vez que se guarda un cambio menor).
    if (!id) {
      const cantidadInicial = document.getElementById("producto-cantidad-inicial").value;
      if (cantidadInicial && Number(cantidadInicial) > 0) {
        const costo = document.getElementById("producto-costo").value;
        if (!costo) {
          toastMensaje = "Producto guardado, pero no se registró el lote inicial: falta el Costo.";
          toastTipo = "error";
        } else {
          try {
            await api.crearLote({
              producto_id: producto.id,
              cantidad_actual: cantidadInicial,
              costo_adquisicion: costo,
              fecha_vencimiento:
                document.getElementById("producto-cantidad-inicial-vencimiento").value || null,
            });
            toastMensaje = "Producto y lote inicial guardados correctamente.";
          } catch (errLote) {
            toastMensaje = `Producto guardado, pero falló el lote inicial: ${errLote.message}`;
            toastTipo = "error";
          }
        }
      }
    }

    await refrescarProductos();
    poblarTablaProductos();
    cargarProductoEnFormulario(producto);
    mostrarToast(toastMensaje, toastTipo);
  } catch (err) {
    alert(`No se pudo guardar el producto: ${err.message}`);
  }
}

// ---------- Panel de notas ----------

async function actualizarPanelNotas(producto) {
  const panel = document.getElementById("panel-notas");
  if (!panel) return;
  panel.hidden = false;
  document.getElementById("notas-producto-nombre").textContent = producto.nombre;

  const notas = await api.listarNotasDeProducto(producto.id);
  const lista = document.getElementById("notas-lista");
  lista.innerHTML = "";
  notas.forEach((nota) => {
    const li = document.createElement("li");
    const span = document.createElement("span");
    span.textContent = nota.texto;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = "Quitar";
    btn.className = "btn-secundario";
    btn.addEventListener("click", async () => {
      await api.eliminarNotaProducto(nota.id);
      actualizarPanelNotas(producto);
    });
    li.appendChild(span);
    li.appendChild(btn);
    lista.appendChild(li);
  });

  document.getElementById("form-nota").onsubmit = async (e) => {
    e.preventDefault();
    const textoEl = document.getElementById("nota-texto");
    try {
      await api.agregarNotaProducto(producto.id, { texto: textoEl.value });
      textoEl.value = "";
      actualizarPanelNotas(producto);
    } catch (err) {
      alert(`No se pudo agregar la nota: ${err.message}`);
    }
  };
}

// ---------- Proveedores (select del formulario de productos) ----------

async function poblarSelectProveedores() {
  const select = document.getElementById("producto-proveedor");
  if (!select) return;
  const proveedores = await api.listarProveedores();
  const actual = select.value;
  select.innerHTML = '<option value="">(ninguno)</option>';
  proveedores.forEach((prov) => {
    const opt = document.createElement("option");
    opt.value = prov.id;
    opt.textContent = prov.nombre;
    select.appendChild(opt);
  });
  select.value = actual;
}

async function actualizarPanelReceta(producto) {
  const panel = document.getElementById("panel-receta");
  if (!panel) return;

  if (producto.tipo !== "compuesto") {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  document.getElementById("receta-producto-nombre").textContent = producto.nombre;

  const select = document.getElementById("receta-insumo");
  select.innerHTML = "";
  state.productos
    .filter((p) => p.id !== producto.id)
    .forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p.id;
      opt.textContent = p.nombre;
      select.appendChild(opt);
    });

  const ingredientes = await api.listarRecetaDeProducto(producto.id);
  const lista = document.getElementById("receta-lista");
  lista.innerHTML = "";
  ingredientes.forEach((ing) => {
    const li = document.createElement("li");
    const span = document.createElement("span");
    span.textContent = `${formatearCantidad(ing.cantidad_requerida)} x ${ing.insumo_nombre}`;
    const btn = document.createElement("button");
    btn.textContent = "Quitar";
    btn.type = "button";
    btn.className = "btn-secundario";
    btn.addEventListener("click", async () => {
      await api.eliminarIngredienteReceta(ing.id);
      actualizarPanelReceta(producto);
    });
    li.appendChild(span);
    li.appendChild(btn);
    lista.appendChild(li);
  });

  document.getElementById("form-receta").onsubmit = async (e) => {
    e.preventDefault();
    const insumoId = Number(select.value);
    const cantidad = document.getElementById("receta-cantidad").value;
    try {
      await api.agregarIngredienteReceta(producto.id, {
        insumo_id: insumoId,
        cantidad_requerida: cantidad,
      });
      document.getElementById("receta-cantidad").value = "";
      actualizarPanelReceta(producto);
    } catch (err) {
      alert(`No se pudo agregar el ingrediente: ${err.message}`);
    }
  };
}

// ---------- Seccion Inventario ----------

let filtroInventarioCategoria = "todas";

async function renderSeccionInventario() {
  const html = await fetch("views/inventario.html").then((r) => r.text());
  appViewEl.innerHTML = html;

  await refrescarProductos();

  renderFiltrosInventario();
  poblarTablaResumenInventario();

  document.getElementById("btn-volver-inventario").addEventListener("click", () => {
    document.getElementById("detalle-inventario-producto").hidden = true;
    document.getElementById("panel-resumen-inventario").hidden = false;
    cancelarEdicionLote();
    // Recargar productos por si se registró/edito un lote y cambió el stock total
    refrescarProductos().then(() => poblarTablaResumenInventario());
  });

  document.getElementById("form-lote").addEventListener("submit", onSubmitLote);
  document.getElementById("btn-cancelar-edicion-lote").addEventListener("click", cancelarEdicionLote);

  const buscador = document.getElementById("inventario-buscador");
  if (buscador) buscador.addEventListener("input", () => poblarTablaResumenInventario());
}

function renderFiltrosInventario() {
  const tabs = document.getElementById("inventario-categorias-tabs");
  if (!tabs) return;
  tabs.innerHTML = "";

  const btnTodas = document.createElement("button");
  btnTodas.className = `categoria-tab ${filtroInventarioCategoria === "todas" ? "activo" : ""}`;
  btnTodas.textContent = "Todas";
  btnTodas.onclick = () => {
    filtroInventarioCategoria = "todas";
    renderFiltrosInventario();
    poblarTablaResumenInventario();
  };
  tabs.appendChild(btnTodas);

  categoriasDisponibles().forEach((cat) => {
    const btn = document.createElement("button");
    btn.className = `categoria-tab ${filtroInventarioCategoria === cat ? "activo" : ""}`;
    btn.textContent = cat;
    btn.onclick = () => {
      filtroInventarioCategoria = cat;
      renderFiltrosInventario();
      poblarTablaResumenInventario();
    };
    tabs.appendChild(btn);
  });
}

function poblarTablaResumenInventario() {
  const body = document.getElementById("inventario-resumen-body");
  if (!body) return;
  body.innerHTML = "";

  const buscadorEl = document.getElementById("inventario-buscador");
  const termino = buscadorEl ? buscadorEl.value.trim().toLowerCase() : "";

  // Los servicios (ej. "Domicilio") no tienen inventario fisico: mostrarlos
  // aqui con "0" se ve como si estuvieran agotados cuando en realidad el
  // concepto de stock no les aplica.
  let productosMostrados = state.productos.filter((p) => !p.es_servicio);

  if (filtroInventarioCategoria !== "todas") {
    productosMostrados = productosMostrados.filter((p) => p.grupo === filtroInventarioCategoria);
  }
  if (termino) {
    productosMostrados = productosMostrados.filter((p) => {
      const enNombre = p.nombre.toLowerCase().includes(termino);
      const enCodigo = (p.codigo_barras || "").toLowerCase().includes(termino);
      const enSku = (p.codigo || "").toLowerCase().includes(termino);
      return enNombre || enCodigo || enSku;
    });
  }

  productosMostrados.forEach((producto) => {
    const stockTotal = Number(producto.stock_total) || 0;
    const umbral = producto.stock_bajo_umbral != null ? Number(producto.stock_bajo_umbral) : null;
    const stockBajo = producto.stock_bajo_activo && umbral != null && stockTotal <= umbral;

    const tr = document.createElement("tr");
    tr.className = "fila-clickable";
    tr.innerHTML = `
      <td>${producto.nombre}</td>
      <td>${producto.grupo || "—"}</td>
      <td>${producto.tipo}</td>
      <td>
        <strong>${formatearCantidad(stockTotal)}</strong> ${etiquetaUnidadMedida(producto.unidad_medida)}
        ${stockBajo ? '<span class="badge-nivel rojo">Stock bajo</span>' : ""}
      </td>
    `;
    tr.addEventListener("click", () => {
      document.getElementById("panel-resumen-inventario").hidden = true;
      document.getElementById("detalle-inventario-producto").hidden = false;
      document.getElementById("lotes-producto-nombre-nuevo").textContent = producto.nombre;
      cargarLotesDeProducto(producto.id);
    });
    body.appendChild(tr);
  });
}

async function cargarLotesDeProducto(productoId) {
  const panelNuevo = document.getElementById("panel-nuevo-lote");
  const panelLotes = document.getElementById("panel-lotes");
  state.inventarioProductoId = productoId;

  if (!productoId) {
    panelNuevo.hidden = true;
    panelLotes.hidden = true;
    return;
  }

  panelNuevo.hidden = false;
  panelLotes.hidden = false;
  const producto = state.productos.find((p) => p.id === productoId);
  document.getElementById("lotes-producto-nombre").textContent = producto ? producto.nombre : "";

  const [lotes, alertas] = await Promise.all([
    api.listarLotesDeProducto(productoId),
    api.semaforoVencimientos({ soloAlertas: false }),
  ]);
  const nivelPorLote = new Map(
    alertas.filter((a) => a.producto_id === productoId).map((a) => [a.id, a.nivel])
  );

  const body = document.getElementById("lotes-tabla-body");
  body.innerHTML = "";
  lotes.forEach((lote) => {
    const nivel = nivelPorLote.get(lote.id);
    const tr = document.createElement("tr");
    tr.className = "fila-clickable";
    tr.innerHTML = `
      <td>${new Date(lote.fecha_ingreso).toLocaleDateString()}</td>
      <td>${formatearCantidad(lote.cantidad_actual)}</td>
      <td>${formatearMoneda(lote.costo_adquisicion)}</td>
      <td>${lote.fecha_vencimiento ? new Date(lote.fecha_vencimiento).toLocaleDateString() : "—"}</td>
      <td>${nivel ? `<span class="badge-nivel ${nivel}">${nivel}</span>` : "—"}</td>
    `;
    tr.addEventListener("click", () => cargarLoteEnFormulario(lote));
    body.appendChild(tr);
  });
}

// Clic en una fila de la tabla de lotes: carga sus valores en el formulario
// de arriba para corregirlos (ej. tras un conteo fisico o un error de
// captura). Mismo patron que "clic en una fila del catalogo" en Productos.
function cargarLoteEnFormulario(lote) {
  document.getElementById("lote-id").value = lote.id;
  document.getElementById("lote-cantidad").value = lote.cantidad_actual;
  document.getElementById("lote-costo").value = formatearInputMoneda(lote.costo_adquisicion);
  document.getElementById("lote-vencimiento").value = lote.fecha_vencimiento
    ? lote.fecha_vencimiento.slice(0, 10)
    : "";
  document.getElementById("btn-guardar-lote").textContent = "Guardar cambios";
  document.getElementById("btn-cancelar-edicion-lote").hidden = false;
}

function cancelarEdicionLote() {
  document.getElementById("form-lote").reset();
  document.getElementById("lote-id").value = "";
  document.getElementById("btn-guardar-lote").textContent = "Registrar lote";
  document.getElementById("btn-cancelar-edicion-lote").hidden = true;
}

async function onSubmitLote(e) {
  e.preventDefault();
  if (!state.inventarioProductoId) return;

  const loteId = document.getElementById("lote-id").value;
  const payload = {
    cantidad_actual: document.getElementById("lote-cantidad").value,
    costo_adquisicion: parsearMoneda(document.getElementById("lote-costo").value),
    fecha_vencimiento: document.getElementById("lote-vencimiento").value || null,
  };

  try {
    if (loteId) {
      await api.editarLote(loteId, payload);
      mostrarToast("Lote actualizado correctamente.");
    } else {
      await api.crearLote({ producto_id: state.inventarioProductoId, ...payload });
      mostrarToast("Lote registrado correctamente.");
    }
    cancelarEdicionLote();
    await cargarLotesDeProducto(state.inventarioProductoId);
    await refrescarProductos(); // el stock_total pudo cambiar
  } catch (err) {
    alert(`No se pudo guardar el lote: ${err.message}`);
  }
}

// ---------- Seccion Alertas ----------

async function renderSeccionAlertas() {
  const html = await fetch("views/alertas.html").then((r) => r.text());
  appViewEl.innerHTML = html;

  const alertas = await api.semaforoVencimientos();
  const body = document.getElementById("alertas-tabla-body");
  const vacio = document.getElementById("alertas-vacio");

  body.innerHTML = "";
  if (alertas.length === 0) {
    vacio.hidden = false;
    return;
  }
  vacio.hidden = true;

  alertas.forEach((a) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><span class="badge-nivel ${a.nivel}">${a.nivel}</span></td>
      <td>${a.producto_nombre}</td>
      <td>${formatearCantidad(a.cantidad_actual)}</td>
      <td>${new Date(a.fecha_vencimiento).toLocaleDateString()}</td>
      <td>${a.dias_restantes}</td>
    `;
    body.appendChild(tr);
  });
}

// ---------- Seccion Configuracion ----------

// Compartido con la seccion Productos (el selector de "impresora destino"
// del formulario se alimenta de esta misma lista).
async function refrescarImpresoras() {
  state.impresoras = await api.listarImpresoras();
}

function poblarSelectImpresoras() {
  const select = document.getElementById("producto-impresora");
  if (!select) return;
  const actual = select.value;
  select.innerHTML = '<option value="">(ninguna)</option>';
  state.impresoras.forEach((imp) => {
    const opt = document.createElement("option");
    opt.value = imp.nombre;
    opt.textContent = imp.nombre;
    select.appendChild(opt);
  });
  select.value = actual;
}

function poblarListaImpresoras() {
  const lista = document.getElementById("impresoras-lista");
  if (!lista) return;
  lista.innerHTML = "";

  state.impresoras.forEach((imp) => {
    const li = document.createElement("li");
    const span = document.createElement("span");
    span.textContent = imp.nombre;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = "Quitar";
    btn.className = "btn-secundario";
    btn.addEventListener("click", async () => {
      await api.eliminarImpresora(imp.id);
      await refrescarImpresoras();
      poblarListaImpresoras();
    });
    li.appendChild(span);
    li.appendChild(btn);
    lista.appendChild(li);
  });
}

async function renderSeccionConfiguracion() {
  const html = await fetch("views/configuracion.html").then((r) => r.text());
  appViewEl.innerHTML = html;

  const negocio = await api.obtenerConfiguracionNegocio();
  document.getElementById("negocio-nombre").value = negocio.nombre_negocio || "";
  document.getElementById("negocio-nit").value = negocio.nit || "";
  document.getElementById("negocio-direccion").value = negocio.direccion || "";
  document.getElementById("negocio-telefono").value = negocio.telefono || "";
  document.getElementById("form-negocio").addEventListener("submit", onSubmitNegocio);

  await refrescarImpresoras();
  poblarListaImpresoras();
  document.getElementById("form-impresora").addEventListener("submit", onSubmitImpresora);

  await poblarListaProveedores();
  document.getElementById("form-proveedor").addEventListener("submit", onSubmitProveedor);
}

async function poblarListaProveedores() {
  const lista = document.getElementById("proveedores-lista");
  if (!lista) return;
  const proveedores = await api.listarProveedores();
  lista.innerHTML = "";
  proveedores.forEach((prov) => {
    const li = document.createElement("li");
    const span = document.createElement("span");
    span.textContent = prov.nombre;
    li.appendChild(span);
    lista.appendChild(li);
  });
}

async function onSubmitProveedor(e) {
  e.preventDefault();
  const nombreEl = document.getElementById("proveedor-nombre");
  try {
    await api.crearProveedor({ nombre: nombreEl.value });
    nombreEl.value = "";
    await poblarListaProveedores();
  } catch (err) {
    alert(`No se pudo agregar el proveedor: ${err.message}`);
  }
}

async function onSubmitNegocio(e) {
  e.preventDefault();
  const payload = {
    nombre_negocio: document.getElementById("negocio-nombre").value || null,
    nit: document.getElementById("negocio-nit").value || null,
    direccion: document.getElementById("negocio-direccion").value || null,
    telefono: document.getElementById("negocio-telefono").value || null,
  };
  try {
    await api.actualizarConfiguracionNegocio(payload);
  } catch (err) {
    alert(`No se pudo guardar la configuracion: ${err.message}`);
  }
}

async function onSubmitImpresora(e) {
  e.preventDefault();
  const nombre = document.getElementById("impresora-nombre").value;
  try {
    await api.crearImpresora({ nombre });
    document.getElementById("impresora-nombre").value = "";
    await refrescarImpresoras();
    poblarListaImpresoras();
  } catch (err) {
    alert(`No se pudo agregar la impresora: ${err.message}`);
  }
}

init();
