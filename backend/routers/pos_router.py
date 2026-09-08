"""
routers/pos_router.py
------------------------
Endpoints del Punto de Venta: creacion de ordenes (directas o por mesa),
adicion de lineas y cierre/pago.

El foco de UX (mantener el cursor en el campo de entrada para el lector de
barras, soportar multiplicadores "5 * codigo") es responsabilidad del
frontend (ver frontend/js/app.js); este router solo recibe ya el
producto_id y la cantidad resuelta.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.inventory import Producto
from backend.models.pos import Orden, OrdenDetalle, EstadoOrden, TipoOrden, Mesa, EstadoMesa
from backend.services.ventas import (
    descontar_inventario_por_venta,
    reponer_inventario_por_devolucion,
    StockInsuficienteError,
)
from backend import schemas

router = APIRouter(prefix="/pos", tags=["POS"])


@router.post("/ordenes", response_model=schemas.OrdenOut, status_code=201)
def crear_orden(payload: schemas.OrdenCreate, db: Session = Depends(get_db)):
    """
    Crea una orden. Si trae `detalles`, se agregan en el mismo paso y se
    descuenta inventario de inmediato (comportamiento de venta directa de
    mostrador). Para el flujo de mesas, normalmente se crea la orden vacia
    primero y se van agregando lineas con POST /pos/ordenes/{id}/detalles
    a medida que el mesero toma pedidos.
    """
    if payload.tipo_orden == TipoOrden.MESA:
        if payload.mesa_id is None:
            raise HTTPException(status_code=422, detail="tipo_orden='mesa' requiere mesa_id")
        mesa = db.get(Mesa, payload.mesa_id)
        if not mesa:
            raise HTTPException(status_code=404, detail="Mesa no encontrada")
        mesa.estado = EstadoMesa.OCUPADA

    orden = Orden(
        tipo_orden=payload.tipo_orden,
        mesa_id=payload.mesa_id,
        atendido_por=payload.atendido_por,
        estado=EstadoOrden.ABIERTA,
    )
    db.add(orden)
    db.flush()  # asigna orden.id sin cerrar la transaccion

    for linea in payload.detalles:
        _agregar_detalle(db, orden, linea.producto_id, linea.cantidad)

    db.commit()
    db.refresh(orden)
    return orden


@router.post("/ordenes/{orden_id}/detalles", response_model=schemas.OrdenOut)
def agregar_detalle(orden_id: int, payload: schemas.OrdenDetalleCreate, db: Session = Depends(get_db)):
    orden = db.get(Orden, orden_id)
    if not orden:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    if orden.estado != EstadoOrden.ABIERTA:
        raise HTTPException(status_code=409, detail="La orden ya no esta abierta")

    _agregar_detalle(db, orden, payload.producto_id, payload.cantidad)
    db.commit()
    db.refresh(orden)
    return orden


def _agregar_detalle(db: Session, orden: Orden, producto_id: int, cantidad):
    producto = db.get(Producto, producto_id)
    if not producto:
        raise HTTPException(status_code=404, detail=f"Producto {producto_id} no encontrado")

    try:
        descontar_inventario_por_venta(db, producto, cantidad)
    except StockInsuficienteError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    detalle = OrdenDetalle(
        orden_id=orden.id,
        producto_id=producto.id,
        cantidad=cantidad,
        # Precio congelado al momento de la venta: la base del futuro
        # calculo contable de utilidad bruta (ver documento maestro, seccion C).
        precio_unitario_historico=producto.precio_venta,
    )
    db.add(detalle)
    return detalle


def _orden_y_detalle_abiertos(db: Session, orden_id: int, detalle_id: int):
    """Valida que la orden exista, siga abierta, y que la linea sea suya."""
    orden = db.get(Orden, orden_id)
    if not orden:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    if orden.estado != EstadoOrden.ABIERTA:
        raise HTTPException(status_code=409, detail="La orden ya no esta abierta")

    detalle = db.get(OrdenDetalle, detalle_id)
    # La comprobacion de pertenencia no es un detalle: sin ella se podria
    # borrar la linea de OTRA orden pasando su id en la ruta.
    if not detalle or detalle.orden_id != orden.id:
        raise HTTPException(status_code=404, detail="Linea no encontrada en esta orden")
    return orden, detalle


@router.delete("/ordenes/{orden_id}/detalles/{detalle_id}", response_model=schemas.OrdenOut)
def eliminar_detalle(orden_id: int, detalle_id: int, db: Session = Depends(get_db)):
    """
    Quita una linea del ticket y devuelve su cantidad al inventario.

    Hace falta porque el inventario se descuenta al AGREGAR la linea, no al
    cobrar: sin este endpoint, todo lo que el cliente se arrepienta de
    llevar queda descontado para siempre.
    """
    orden, detalle = _orden_y_detalle_abiertos(db, orden_id, detalle_id)
    reponer_inventario_por_devolucion(db, detalle.producto, detalle.cantidad)
    db.delete(detalle)
    db.commit()
    db.refresh(orden)
    return orden


@router.put("/ordenes/{orden_id}/detalles/{detalle_id}", response_model=schemas.OrdenOut)
def cambiar_cantidad_detalle(
    orden_id: int,
    detalle_id: int,
    payload: schemas.OrdenDetalleUpdate,
    db: Session = Depends(get_db),
):
    """
    Cambia la cantidad de una linea, moviendo el inventario solo por la
    DIFERENCIA: subir de 2 a 5 descuenta 3, bajar de 5 a 2 devuelve 3. Asi
    no hace falta deshacer y rehacer la linea entera.
    """
    orden, detalle = _orden_y_detalle_abiertos(db, orden_id, detalle_id)

    if payload.cantidad <= 0:
        raise HTTPException(
            status_code=422,
            detail="La cantidad debe ser mayor que cero. Para quitar la linea, usa DELETE.",
        )

    diferencia = payload.cantidad - detalle.cantidad
    if diferencia > 0:
        try:
            descontar_inventario_por_venta(db, detalle.producto, diferencia)
        except StockInsuficienteError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    elif diferencia < 0:
        reponer_inventario_por_devolucion(db, detalle.producto, -diferencia)

    detalle.cantidad = payload.cantidad
    db.commit()
    db.refresh(orden)
    return orden


@router.post("/ordenes/{orden_id}/pagar", response_model=schemas.OrdenOut)
def pagar_orden(orden_id: int, db: Session = Depends(get_db)):
    orden = db.get(Orden, orden_id)
    if not orden:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    if orden.estado != EstadoOrden.ABIERTA:
        raise HTTPException(status_code=409, detail="La orden ya no esta abierta")

    orden.estado = EstadoOrden.PAGADA
    orden.fecha_cierre = datetime.now(timezone.utc)

    if orden.mesa_id:
        mesa = db.get(Mesa, orden.mesa_id)
        if mesa:
            mesa.estado = EstadoMesa.LIBRE

    db.commit()
    db.refresh(orden)
    return orden


@router.get("/ordenes/{orden_id}", response_model=schemas.OrdenOut)
def obtener_orden(orden_id: int, db: Session = Depends(get_db)):
    orden = db.get(Orden, orden_id)
    if not orden:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    return orden


@router.get("/mesas", response_model=list[schemas.MesaOut])
def listar_mesas(db: Session = Depends(get_db)):
    return db.query(Mesa).filter(Mesa.activa.is_(True)).order_by(Mesa.nombre).all()


@router.post("/mesas", response_model=schemas.MesaOut, status_code=201)
def crear_mesa(payload: schemas.MesaCreate, db: Session = Depends(get_db)):
    mesa = Mesa(nombre=payload.nombre, capacidad=payload.capacidad)
    db.add(mesa)
    db.commit()
    db.refresh(mesa)
    return mesa


@router.get("/mesas/{mesa_id}/orden-abierta", response_model=schemas.OrdenOut | None)
def obtener_orden_abierta_de_mesa(mesa_id: int, db: Session = Depends(get_db)):
    """
    Recupera la cuenta abierta vinculada a una mesa (si existe). El frontend
    la usa al seleccionar una mesa ya ocupada, para seguir agregando lineas
    a la misma cuenta en vez de crear una nueva.
    """
    return (
        db.query(Orden)
        .filter(Orden.mesa_id == mesa_id, Orden.estado == EstadoOrden.ABIERTA)
        .order_by(Orden.fecha_creacion.desc())
        .first()
    )
