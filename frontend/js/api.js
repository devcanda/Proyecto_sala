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

  // Inventario
  listarProductos: () => apiRequest("/inventario/productos"),
  buscarProductoPorCodigo: (codigo) =>
    apiRequest(`/inventario/productos/codigo/${encodeURIComponent(codigo)}`),

  // Alertas
  semaforoVencimientos: () => apiRequest("/alertas/vencimientos"),

  // POS
  listarMesas: () => apiRequest("/pos/mesas"),
  ordenAbiertaDeMesa: (mesaId) => apiRequest(`/pos/mesas/${mesaId}/orden-abierta`),
  crearOrden: (payload) => apiRequest("/pos/ordenes", { method: "POST", body: payload }),
  agregarDetalle: (ordenId, payload) =>
    apiRequest(`/pos/ordenes/${ordenId}/detalles`, { method: "POST", body: payload }),
  pagarOrden: (ordenId) => apiRequest(`/pos/ordenes/${ordenId}/pagar`, { method: "POST" }),
  obtenerOrden: (ordenId) => apiRequest(`/pos/ordenes/${ordenId}`),
};
