"""
models/inventory.py
--------------------
Modelos de Catalogo e Inventario.

Diseno pensado para dos casos de uso simultaneos:

1. Retail (salsamentarias, minimarkets): productos por unidad o por peso,
   con lotes que vencen y deben salir por FIFO.
2. Hospitalidad (restaurantes/bares): productos "compuestos" (escandallos)
   que descuentan de otros productos (insumos) al venderse. Ej: 1 Mojito
   descuenta ron, azucar, limon y un vaso desde `recetas_ingredientes`.

Todas las tablas dejan sentada la base contable (Modulo C del documento
maestro): `costo_adquisicion` en cada lote permite calcular utilidad bruta
en fases posteriores sin rediseñar el esquema.
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


class TipoProducto(str, enum.Enum):
    UNIDAD = "unidad"      # Se vende por pieza entera (ej. gaseosa, paquete)
    PESO = "peso"          # Se vende por gramos/kg (ej. queso, carnes frias)
    COMPUESTO = "compuesto"  # Escandallo: producto final armado desde insumos


class UnidadMedida(str, enum.Enum):
    """
    Metadato informativo del producto (no altera la logica de venta/FIFO,
    que sigue gobernada por TipoProducto): a pedido del desarrollador,
    lista fija en vez de texto libre, para evitar "kg" vs "Kg" vs "kilo".
    """
    UNIDAD = "unidad"
    KG = "kg"
    GRAMO = "gramo"
    LITRO = "litro"
    MILILITRO = "mililitro"
    LIBRA = "libra"


class Proveedor(Base):
    """Catalogo minimo de proveedores (solo nombre por ahora)."""
    __tablename__ = "proveedores"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(150), nullable=False)

    def __repr__(self) -> str:
        return f"<Proveedor id={self.id} nombre={self.nombre!r}>"


class Producto(Base):
    """
    Catalogo central de productos vendibles e insumos.

    `impresora_destino` habilita el ruteo de comandas en modo Hospitalidad
    (ej. "barra", "cocina"); en modo Retail normalmente queda vacio/None.

    `costo` es un costo de REFERENCIA a nivel de producto (para calcular el
    margen de ganancia en la UI); es distinto de `costo_adquisicion` de
    cada `LoteInventario`, que es el costo real de esa compra especifica y
    el que se usa para la utilidad bruta real del Modulo Contable.

    `es_servicio=True` significa que el producto NO tiene inventario fisico
    (ej. una cuota de instalacion, un servicio de domicilio): vender un
    servicio no debe intentar descontar lotes (ver
    services/ventas.py:descontar_inventario_por_venta).

    `imagen` solo se llena a traves de POST /inventario/productos/{id}/imagen
    (ver inv_router.py); nunca se escribe desde create/update directo.
    """
    __tablename__ = "productos"

    id = Column(Integer, primary_key=True, index=True)
    codigo_barras = Column(String(64), unique=True, index=True, nullable=True)
    codigo = Column(String(50), nullable=True)  # SKU interno, texto libre del negocio
    nombre = Column(String(150), nullable=False)
    tipo = Column(Enum(TipoProducto), nullable=False, default=TipoProducto.UNIDAD)
    unidad_medida = Column(Enum(UnidadMedida), nullable=False, default=UnidadMedida.UNIDAD)
    precio_venta = Column(Numeric(12, 2), nullable=False, default=0)
    costo = Column(Numeric(12, 2), nullable=True)
    incluye_impuesto = Column(Boolean, default=False, nullable=False)
    # Texto libre (ej. "Lacteos", "Embutidos"), no una tabla aparte: alcanza
    # para agrupar/filtrar la grilla de Retail sin la complejidad de un CRUD
    # de grupos propio.
    grupo = Column(String(80), nullable=True, index=True)
    descripcion = Column(String(2000), nullable=True)
    es_servicio = Column(Boolean, default=False, nullable=False)
    proveedor_id = Column(Integer, ForeignKey("proveedores.id"), nullable=True)
    stock_bajo_activo = Column(Boolean, default=False, nullable=False)
    stock_bajo_umbral = Column(Numeric(12, 3), nullable=True)
    imagen = Column(String(255), nullable=True)
    impresora_destino = Column(String(50), nullable=True)
    activo = Column(Boolean, default=True, nullable=False)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    lotes = relationship("LoteInventario", back_populates="producto", cascade="all, delete-orphan")
    proveedor = relationship("Proveedor")
    notas = relationship("NotaProducto", back_populates="producto", cascade="all, delete-orphan")

    # Si este producto es un escandallo (tipo=COMPUESTO), aqui viven sus
    # ingredientes. Si es un insumo, `usado_en` lista los escandallos que lo
    # consumen.
    ingredientes = relationship(
        "RecetaIngrediente",
        foreign_keys="RecetaIngrediente.producto_compuesto_id",
        back_populates="producto_compuesto",
        cascade="all, delete-orphan",
    )
    usado_en = relationship(
        "RecetaIngrediente",
        foreign_keys="RecetaIngrediente.insumo_id",
        back_populates="insumo",
    )

    def __repr__(self) -> str:
        return f"<Producto id={self.id} nombre={self.nombre!r} tipo={self.tipo}>"

    @property
    def stock_total(self):
        """Suma de la cantidad actual de todos sus lotes."""
        return sum((lote.cantidad_actual for lote in self.lotes), 0)


class NotaProducto(Base):
    """Notas libres adjuntas a un producto, agregables/eliminables desde la UI."""
    __tablename__ = "notas_producto"

    id = Column(Integer, primary_key=True, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    texto = Column(String(500), nullable=False)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())

    producto = relationship("Producto", back_populates="notas")


class RecetaIngrediente(Base):
    """
    Tabla pivote de escandallos: define cuanto de `insumo_id` se descuenta
    del inventario cada vez que se vende una unidad de `producto_compuesto_id`.
    """
    __tablename__ = "recetas_ingredientes"

    id = Column(Integer, primary_key=True, index=True)
    producto_compuesto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    insumo_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad_requerida = Column(Numeric(12, 3), nullable=False)  # admite decimales (ej. 0.05 kg)

    producto_compuesto = relationship(
        "Producto", foreign_keys=[producto_compuesto_id], back_populates="ingredientes"
    )
    insumo = relationship("Producto", foreign_keys=[insumo_id], back_populates="usado_en")


class LoteInventario(Base):
    """
    Existencias fisicas de un producto, controladas por lote para permitir
    trazabilidad FIFO y semaforizacion de vencimientos.

    `costo_adquisicion` es el costo unitario de ESTE lote especifico (puede
    variar entre lotes del mismo producto por compras en fechas distintas),
    y es la base para el calculo de utilidad bruta en el Modulo Contable.
    """
    __tablename__ = "lotes_inventario"

    id = Column(Integer, primary_key=True, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad_actual = Column(Numeric(12, 3), nullable=False, default=0)
    costo_adquisicion = Column(Numeric(12, 2), nullable=False)
    fecha_ingreso = Column(DateTime(timezone=True), server_default=func.now())
    fecha_vencimiento = Column(DateTime(timezone=True), nullable=True)

    producto = relationship("Producto", back_populates="lotes")

    def __repr__(self) -> str:
        return (
            f"<LoteInventario id={self.id} producto_id={self.producto_id} "
            f"cantidad={self.cantidad_actual} vence={self.fecha_vencimiento}>"
        )
