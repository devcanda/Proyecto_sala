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

from backend.models.inventory import TipoProducto
from backend.models.pos import TipoOrden, EstadoOrden, EstadoMesa


# ---------- Productos ----------

class ProductoBase(BaseModel):
    codigo_barras: Optional[str] = None
    nombre: str
    tipo: TipoProducto = TipoProducto.UNIDAD
    precio_venta: Decimal
    impresora_destino: Optional[str] = None


class ProductoCreate(ProductoBase):
    pass


class ProductoOut(ProductoBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    activo: bool


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


class LoteAlerta(LoteInventarioOut):
    """Lote incluido en el dashboard de semaforizacion."""
    producto_nombre: str
    dias_restantes: int
    nivel: str  # "rojo" | "amarillo" | "verde"


# ---------- Mesas ----------

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
