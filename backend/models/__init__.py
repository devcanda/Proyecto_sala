"""
Importar todos los modelos aqui asegura que queden registrados en
Base.metadata antes de llamar a Base.metadata.create_all(), sin importar
el orden en que los importe el resto de la aplicacion.
"""
from backend.models.inventory import Producto, RecetaIngrediente, LoteInventario, TipoProducto  # noqa: F401
from backend.models.pos import Mesa, Orden, OrdenDetalle, TipoOrden, EstadoOrden, EstadoMesa  # noqa: F401

__all__ = [
    "Producto",
    "RecetaIngrediente",
    "LoteInventario",
    "TipoProducto",
    "Mesa",
    "Orden",
    "OrdenDetalle",
    "TipoOrden",
    "EstadoOrden",
    "EstadoMesa",
]
