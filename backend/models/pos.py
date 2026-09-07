"""
models/pos.py
--------------
Modelos del Punto de Venta (POS).

`Mesa` solo tiene sentido en modo Hospitalidad (restaurantes/bares); en modo
Retail las ordenes se crean con tipo_orden="directa" y mesa_id=None.

`orden_detalles.precio_unitario_historico` congela el precio de venta en el
momento de la transaccion: aunque el precio del producto cambie despues,
el ticket historico no se altera. Junto con `costo_adquisicion` del lote
consumido (ver services/ventas para la logica FIFO), esto deja lista la
base para el Modulo Contable (utilidad bruta = precio_unitario_historico -
costo_adquisicion, por linea).
"""
import enum

from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    DateTime,
    Enum,
    ForeignKey,
    Boolean,
    func,
)
from sqlalchemy.orm import relationship

from backend.database import Base


class EstadoMesa(str, enum.Enum):
    LIBRE = "libre"
    OCUPADA = "ocupada"
    RESERVADA = "reservada"


class Mesa(Base):
    """Mapa del local. Solo aplica en modo Hospitalidad."""
    __tablename__ = "mesas"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(50), nullable=False)  # ej. "Mesa 4", "Barra 2"
    capacidad = Column(Integer, nullable=True)
    estado = Column(Enum(EstadoMesa), nullable=False, default=EstadoMesa.LIBRE)
    activa = Column(Boolean, default=True, nullable=False)

    ordenes = relationship("Orden", back_populates="mesa")

    def __repr__(self) -> str:
        return f"<Mesa id={self.id} nombre={self.nombre!r} estado={self.estado}>"


class TipoOrden(str, enum.Enum):
    DIRECTA = "directa"  # Retail: venta de mostrador, se cobra al instante
    MESA = "mesa"        # Hospitalidad: cuenta abierta vinculada a una mesa


class EstadoOrden(str, enum.Enum):
    ABIERTA = "abierta"
    PAGADA = "pagada"
    CANCELADA = "cancelada"


class Orden(Base):
    """Cabecera del ticket / cuenta."""
    __tablename__ = "ordenes"

    id = Column(Integer, primary_key=True, index=True)
    tipo_orden = Column(Enum(TipoOrden), nullable=False, default=TipoOrden.DIRECTA)
    mesa_id = Column(Integer, ForeignKey("mesas.id"), nullable=True)
    estado = Column(Enum(EstadoOrden), nullable=False, default=EstadoOrden.ABIERTA)
    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now())
    fecha_cierre = Column(DateTime(timezone=True), nullable=True)

    # Usuario/cajero que atendio la orden. Se referencia por email/username
    # simple por ahora; un modelo Usuario completo (roles, permisos) queda
    # para una fase posterior de autenticacion.
    atendido_por = Column(String(150), nullable=True)

    mesa = relationship("Mesa", back_populates="ordenes")
    detalles = relationship("OrdenDetalle", back_populates="orden", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Orden id={self.id} tipo={self.tipo_orden} estado={self.estado}>"


class OrdenDetalle(Base):
    """
    Linea de un ticket. `cantidad` acepta decimales para soportar ventas
    por peso (ej. 0.350 kg de jamon).
    """
    __tablename__ = "orden_detalles"

    id = Column(Integer, primary_key=True, index=True)
    orden_id = Column(Integer, ForeignKey("ordenes.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Numeric(12, 3), nullable=False, default=1)
    precio_unitario_historico = Column(Numeric(12, 2), nullable=False)

    orden = relationship("Orden", back_populates="detalles")
    producto = relationship("Producto")

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario_historico

    def __repr__(self) -> str:
        return (
            f"<OrdenDetalle id={self.id} orden_id={self.orden_id} "
            f"producto_id={self.producto_id} cantidad={self.cantidad}>"
        )
