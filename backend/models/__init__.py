"""
Importar todos los modelos aqui asegura que queden registrados en
Base.metadata antes de llamar a Base.metadata.create_all(), sin importar
el orden en que los importe el resto de la aplicacion.
"""
from backend.models.inventory import (  # noqa: F401
    Producto,
    RecetaIngrediente,
    LoteInventario,
    TipoProducto,
    UnidadMedida,
    Proveedor,
    NotaProducto,
)
from backend.models.pos import Mesa, Orden, OrdenDetalle, TipoOrden, EstadoOrden, EstadoMesa  # noqa: F401
from backend.models.config import ConfiguracionNegocio, Impresora  # noqa: F401

__all__ = [
    "Producto",
    "RecetaIngrediente",
    "LoteInventario",
    "TipoProducto",
    "UnidadMedida",
    "Proveedor",
    "NotaProducto",
    "Mesa",
    "Orden",
    "OrdenDetalle",
    "TipoOrden",
    "EstadoOrden",
    "EstadoMesa",
    "ConfiguracionNegocio",
    "Impresora",
]
