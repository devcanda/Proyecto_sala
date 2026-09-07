/**
 * api.js
 * -------
 * Cliente delgado sobre fetch para hablar con el backend FastAPI.
 * Centralizado aqui para que empaquetar como Tauri/Electron solo requiera
 * cambiar API_BASE_URL (ej. si el backend corre embebido vs en la red LAN).
 */
const API_BASE_URL = window.SALSA_POS_API_BASE_URL || "http://127.0.0.1:8000";

async function apiRequest(path, { method = "GET", body } = {}) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch (_) {
      /* respuesta sin cuerpo JSON */
    }
    throw new Error(detail);
  }

  if (res.status === 204) return null;
  return res.json();
}

const api = {
  salud: () => apiRequest("/"),

  // Arma la URL de una imagen de producto ya subida (ver subirImagenProducto).
  urlImagen: (nombreArchivo) => `${API_BASE_URL}/media/${nombreArchivo}`,

  // Inventario: productos
  listarProductos: () => apiRequest("/inventario/productos"),
  buscarProductoPorCodigo: (codigo) =>
    apiRequest(`/inventario/productos/codigo/${encodeURIComponent(codigo)}`),
  crearProducto: (payload) => apiRequest("/inventario/productos", { method: "POST", body: payload }),
  editarProducto: (productoId, payload) =>
    apiRequest(`/inventario/productos/${productoId}`, { method: "PUT", body: payload }),

  // Inventario: recetas de escandallo
  listarRecetaDeProducto: (productoId) => apiRequest(`/inventario/productos/${productoId}/receta`),
  agregarIngredienteReceta: (productoId, payload) =>
    apiRequest(`/inventario/productos/${productoId}/receta`, { method: "POST", body: payload }),
  eliminarIngredienteReceta: (ingredienteId) =>
    apiRequest(`/inventario/recetas/${ingredienteId}`, { method: "DELETE" }),

  // Inventario: lotes
  listarLotesDeProducto: (productoId) => apiRequest(`/inventario/lotes/producto/${productoId}`),
  crearLote: (payload) => apiRequest("/inventario/lotes", { method: "POST", body: payload }),
  editarLote: (loteId, payload) => apiRequest(`/inventario/lotes/${loteId}`, { method: "PUT", body: payload }),

  // Inventario: proveedores
  listarProveedores: () => apiRequest("/inventario/proveedores"),
  crearProveedor: (payload) => apiRequest("/inventario/proveedores", { method: "POST", body: payload }),

  // Inventario: notas de producto
  listarNotasDeProducto: (productoId) => apiRequest(`/inventario/productos/${productoId}/notas`),
  agregarNotaProducto: (productoId, payload) =>
    apiRequest(`/inventario/productos/${productoId}/notas`, { method: "POST", body: payload }),
  eliminarNotaProducto: (notaId) => apiRequest(`/inventario/notas/${notaId}`, { method: "DELETE" }),

  // Inventario: imagen de producto (multipart, no pasa por apiRequest/JSON)
  subirImagenProducto: async (productoId, archivo) => {
    const formData = new FormData();
    formData.append("archivo", archivo);
    const res = await fetch(`${API_BASE_URL}/inventario/productos/${productoId}/imagen`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const data = await res.json();
        detail = data.detail || detail;
      } catch (_) {
        /* respuesta sin cuerpo JSON */
      }
      throw new Error(detail);
    }
    return res.json();
  },

  // Alertas
  semaforoVencimientos: ({ soloAlertas = true } = {}) =>
    apiRequest(`/alertas/vencimientos?solo_alertas=${soloAlertas}`),

  // Configuracion
  obtenerConfiguracionNegocio: () => apiRequest("/config/negocio"),
  actualizarConfiguracionNegocio: (payload) =>
    apiRequest("/config/negocio", { method: "PUT", body: payload }),
  listarImpresoras: () => apiRequest("/config/impresoras"),
  crearImpresora: (payload) => apiRequest("/config/impresoras", { method: "POST", body: payload }),
  eliminarImpresora: (impresoraId) =>
    apiRequest(`/config/impresoras/${impresoraId}`, { method: "DELETE" }),

  // POS
  listarMesas: () => apiRequest("/pos/mesas"),
  crearMesa: (payload) => apiRequest("/pos/mesas", { method: "POST", body: payload }),
  ordenAbiertaDeMesa: (mesaId) => apiRequest(`/pos/mesas/${mesaId}/orden-abierta`),
  crearOrden: (payload) => apiRequest("/pos/ordenes", { method: "POST", body: payload }),
  agregarDetalle: (ordenId, payload) =>
    apiRequest(`/pos/ordenes/${ordenId}/detalles`, { method: "POST", body: payload }),
  pagarOrden: (ordenId) => apiRequest(`/pos/ordenes/${ordenId}/pagar`, { method: "POST" }),
  obtenerOrden: (ordenId) => apiRequest(`/pos/ordenes/${ordenId}`),
};
