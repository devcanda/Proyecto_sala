"""
schemas.py
-----------
Modelos Pydantic (DTOs) usados en request/response de la API. Se mantienen
separados de los modelos SQLAlchemy (backend/models/) a proposito: el ORM
describe como se guardan los datos, estos esquemas describen el contrato
publico de la API y pueden evolucionar de forma independiente.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict

from backend.models.inventory import TipoProducto, UnidadMedida
from backend.models.pos import TipoOrden, EstadoOrden, EstadoMesa


# ---------- Proveedores ----------

class ProveedorCreate(BaseModel):
    nombre: str


class ProveedorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str


# ---------- Productos ----------

class ProductoBase(BaseModel):
    codigo_barras: Optional[str] = None
    codigo: Optional[str] = None
    nombre: str
    tipo: TipoProducto = TipoProducto.UNIDAD
    unidad_medida: UnidadMedida = UnidadMedida.UNIDAD
    precio_venta: Decimal
    costo: Optional[Decimal] = None
    incluye_impuesto: bool = False
    grupo: Optional[str] = None
    descripcion: Optional[str] = None
    es_servicio: bool = False
    proveedor_id: Optional[int] = None
    stock_bajo_activo: bool = False
    stock_bajo_umbral: Optional[Decimal] = None
    impresora_destino: Optional[str] = None
    activo: bool = True


class ProductoCreate(ProductoBase):
    pass


class ProductoOut(ProductoBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    imagen: Optional[str] = None
    stock_total: Decimal = Decimal("0")


class ProductoUpdate(BaseModel):
    """Todos los campos opcionales: PUT solo actualiza lo que venga informado."""
    codigo_barras: Optional[str] = None
    codigo: Optional[str] = None
    nombre: Optional[str] = None
    tipo: Optional[TipoProducto] = None
    unidad_medida: Optional[UnidadMedida] = None
    precio_venta: Optional[Decimal] = None
    costo: Optional[Decimal] = None
    incluye_impuesto: Optional[bool] = None
    grupo: Optional[str] = None
    descripcion: Optional[str] = None
    es_servicio: Optional[bool] = None
    proveedor_id: Optional[int] = None
    stock_bajo_activo: Optional[bool] = None
    stock_bajo_umbral: Optional[Decimal] = None
    impresora_destino: Optional[str] = None
    activo: Optional[bool] = None


# ---------- Notas de producto ----------

class NotaProductoCreate(BaseModel):
    texto: str


class NotaProductoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    producto_id: int
    texto: str
    creado_en: datetime


# ---------- Recetas de escandallo ----------

class RecetaIngredienteCreate(BaseModel):
    insumo_id: int
    cantidad_requerida: Decimal


class RecetaIngredienteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    producto_compuesto_id: int
    insumo_id: int
    cantidad_requerida: Decimal
    insumo_nombre: str


# ---------- Lotes de inventario ----------

class LoteInventarioCreate(BaseModel):
    producto_id: int
    cantidad_actual: Decimal
    costo_adquisicion: Decimal
    fecha_vencimiento: Optional[datetime] = None


class LoteInventarioOut(LoteInventarioCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    fecha_ingreso: datetime


class LoteInventarioUpdate(BaseModel):
    """
    Correccion manual de un lote existente (ej. tras un conteo fisico o un
    error de captura). Todos los campos opcionales: PUT solo actualiza lo
    que venga informado.
    """
    cantidad_actual: Optional[Decimal] = None
    costo_adquisicion: Optional[Decimal] = None
    fecha_vencimiento: Optional[datetime] = None


class LoteAlerta(LoteInventarioOut):
    """Lote incluido en el dashboard de semaforizacion."""
    producto_nombre: str
    dias_restantes: int
    nivel: str  # "rojo" | "amarillo" | "verde"


# ---------- Mesas ----------

class MesaCreate(BaseModel):
    nombre: str
    capacidad: Optional[int] = None


class MesaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    capacidad: Optional[int] = None
    estado: EstadoMesa
    activa: bool


# ---------- Ordenes ----------

class OrdenDetalleCreate(BaseModel):
    producto_id: int
    cantidad: Decimal = Decimal("1")


class OrdenDetalleUpdate(BaseModel):
    """
    Cambio de cantidad de una linea ya registrada (boton "F4 Cantidad" de la
    pantalla de venta). El ajuste de inventario lo calcula el router por
    diferencia contra la cantidad anterior, no se recibe de fuera.
    """
    cantidad: Decimal


class OrdenCreate(BaseModel):
    tipo_orden: TipoOrden = TipoOrden.DIRECTA
    mesa_id: Optional[int] = None
    atendido_por: Optional[str] = None
    detalles: list[OrdenDetalleCreate] = []


class OrdenDetalleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    producto_id: int
    cantidad: Decimal
    precio_unitario_historico: Decimal


class OrdenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tipo_orden: TipoOrden
    mesa_id: Optional[int] = None
    estado: EstadoOrden
    fecha_creacion: datetime
    fecha_cierre: Optional[datetime] = None
    atendido_por: Optional[str] = None
    detalles: list[OrdenDetalleOut] = []


# ---------- Configuracion ----------

class ConfiguracionNegocioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    nombre_negocio: Optional[str] = None
    nit: Optional[str] = None
    direccion: Optional[str] = None
    telefono: Optional[str] = None


class ConfiguracionNegocioUpdate(BaseModel):
    nombre_negocio: Optional[str] = None
    nit: Optional[str] = None
    direccion: Optional[str] = None
    telefono: Optional[str] = None


class ImpresoraCreate(BaseModel):
    nombre: str


class ImpresoraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
