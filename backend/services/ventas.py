"""
services/ventas.py
--------------------
Logica de negocio del descuento de inventario al vender.

Dos reglas conviven aqui:

1. FIFO: al vender un producto simple (unidad o peso), se descuenta primero
   del lote con `fecha_ingreso` mas antigua que aun tenga existencia, y si
   no alcanza, se sigue con el siguiente lote. Esto es lo que permite que
   la semaforizacion de vencimientos (alert_router) tenga sentido: los
   lotes viejos siempre salen primero.

2. Escandallos: si el producto vendido es de tipo COMPUESTO (ej. un
   Mojito), no se descuenta un lote propio -- se expande su receta
   (recetas_ingredientes) y se aplica la regla FIFO recursivamente sobre
   cada insumo, multiplicando `cantidad_requerida` por la cantidad vendida.

Se mantiene independiente de FastAPI (no recibe `Request`/`Response`) para
poder reutilizarse desde otros contextos (ej. scripts de IA, tests).
"""
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.models.inventory import Producto, LoteInventario, TipoProducto


class StockInsuficienteError(Exception):
    """Se lanza cuando no hay existencia suficiente para completar la venta."""

    def __init__(self, producto: Producto, faltante: Decimal):
        self.producto = producto
        self.faltante = faltante
        super().__init__(
            f"Stock insuficiente para '{producto.nombre}': faltan {faltante} unidades."
        )


def _descontar_fifo(db: Session, producto: Producto, cantidad: Decimal) -> None:
    """Descuenta `cantidad` del inventario de un producto simple, mas antiguo primero."""
    restante = cantidad
    lotes = (
        db.query(LoteInventario)
        .filter(LoteInventario.producto_id == producto.id)
        .filter(LoteInventario.cantidad_actual > 0)
        .order_by(LoteInventario.fecha_ingreso.asc())
        .all()
    )

    for lote in lotes:
        if restante <= 0:
            break
        tomar = min(lote.cantidad_actual, restante)
        lote.cantidad_actual -= tomar
        restante -= tomar

    if restante > 0:
        raise StockInsuficienteError(producto, restante)


def descontar_inventario_por_venta(db: Session, producto: Producto, cantidad: Decimal) -> None:
    """
    Punto de entrada unico para descontar inventario de una linea de venta.
    Expande recursivamente si el producto es un escandallo (COMPUESTO).

    Un producto marcado `es_servicio=True` no tiene inventario fisico (ej.
    una instalacion, un domicilio): vender un servicio no descuenta nada.
    """
    if producto.es_servicio:
        return

    if producto.tipo == TipoProducto.COMPUESTO:
        for ingrediente in producto.ingredientes:
            cantidad_insumo = ingrediente.cantidad_requerida * cantidad
            descontar_inventario_por_venta(db, ingrediente.insumo, cantidad_insumo)
    else:
        _descontar_fifo(db, producto, cantidad)
