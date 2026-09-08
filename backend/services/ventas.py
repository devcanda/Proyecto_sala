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


def _reponer_fifo(db: Session, producto: Producto, cantidad: Decimal) -> None:
    """
    Devuelve `cantidad` al inventario de un producto simple.

    LIMITACION CONOCIDA: no se registra de que lote salio cada venta, asi
    que una devolucion no se puede imputar con exactitud al lote original.
    Se devuelve al lote mas antiguo con existencia, que es justamente el que
    FIFO habria consumido primero; para el caso real de este boton --
    deshacer una linea que se acaba de agregar -- coincide siempre.

    Solo puede desviar la atribucion de costo en un caso rebuscado: que la
    venta original vaciara un lote y siguiera en el siguiente, y que se
    deshaga mucho despues. Revertir con exactitud exige guardar el lote (o
    los lotes) consumidos por cada linea, que esta en el backlog.
    """
    lote = (
        db.query(LoteInventario)
        .filter(LoteInventario.producto_id == producto.id)
        .filter(LoteInventario.cantidad_actual > 0)
        .order_by(LoteInventario.fecha_ingreso.asc())
        .first()
    )

    if lote is None:
        # La venta dejo el producto en cero: se reabre el lote mas antiguo
        # que exista, aunque este vacio.
        lote = (
            db.query(LoteInventario)
            .filter(LoteInventario.producto_id == producto.id)
            .order_by(LoteInventario.fecha_ingreso.asc())
            .first()
        )

    if lote is None:
        # Ni siquiera hay lotes (producto vendido sin existencia previa):
        # se crea uno para no perder la devolucion en el aire.
        lote = LoteInventario(
            producto_id=producto.id,
            cantidad_actual=Decimal("0"),
            costo_adquisicion=producto.costo or Decimal("0"),
        )
        db.add(lote)

    lote.cantidad_actual += cantidad


def reponer_inventario_por_devolucion(db: Session, producto: Producto, cantidad: Decimal) -> None:
    """
    Inverso de descontar_inventario_por_venta(). Se usa al quitar una linea
    del ticket o al bajarle la cantidad, para que el stock no quede
    descontado por una venta que no llego a ocurrir.

    Mantiene las mismas dos reglas que el descuento: los servicios no mueven
    inventario, y los productos compuestos expanden su receta.
    """
    if producto.es_servicio:
        return

    if producto.tipo == TipoProducto.COMPUESTO:
        for ingrediente in producto.ingredientes:
            cantidad_insumo = ingrediente.cantidad_requerida * cantidad
            reponer_inventario_por_devolucion(db, ingrediente.insumo, cantidad_insumo)
    else:
        _reponer_fifo(db, producto, cantidad)


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
