"""
routers/inv_router.py
-----------------------
Endpoints de catalogo (productos) e inventario (lotes).

La logica de descuento de stock al vender vive en services/ (FIFO +
escandallos), no aqui: este router solo expone altas/consultas basicas de
catalogo e ingreso de mercancia.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.inventory import Producto, LoteInventario
from backend import schemas

router = APIRouter(prefix="/inventario", tags=["Inventario"])


@router.get("/productos", response_model=list[schemas.ProductoOut])
def listar_productos(solo_activos: bool = True, db: Session = Depends(get_db)):
    query = db.query(Producto)
    if solo_activos:
        query = query.filter(Producto.activo.is_(True))
    return query.order_by(Producto.nombre).all()


@router.get("/productos/codigo/{codigo_barras}", response_model=schemas.ProductoOut)
def obtener_producto_por_codigo(codigo_barras: str, db: Session = Depends(get_db)):
    """
    Endpoint pensado para el flujo de lector de codigo de barras: el
    frontend envia el codigo escaneado y recibe el producto listo para
    agregar a la orden actual.
    """
    producto = db.query(Producto).filter(Producto.codigo_barras == codigo_barras).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado para ese codigo de barras")
    return producto


@router.post("/productos", response_model=schemas.ProductoOut, status_code=201)
def crear_producto(payload: schemas.ProductoCreate, db: Session = Depends(get_db)):
    if payload.codigo_barras:
        existente = db.query(Producto).filter(Producto.codigo_barras == payload.codigo_barras).first()
        if existente:
            raise HTTPException(status_code=409, detail="Ya existe un producto con ese codigo de barras")

    producto = Producto(**payload.model_dump())
    db.add(producto)
    db.commit()
    db.refresh(producto)
    return producto


@router.post("/lotes", response_model=schemas.LoteInventarioOut, status_code=201)
def registrar_lote(payload: schemas.LoteInventarioCreate, db: Session = Depends(get_db)):
    """
    Ingreso de mercancia. Cada llamada crea un lote NUEVO en vez de sumar
    a uno existente, para preservar trazabilidad FIFO (distintos costos y
    fechas de vencimiento por compra).
    """
    producto = db.get(Producto, payload.producto_id)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    lote = LoteInventario(**payload.model_dump())
    db.add(lote)
    db.commit()
    db.refresh(lote)
    return lote


@router.get("/lotes/producto/{producto_id}", response_model=list[schemas.LoteInventarioOut])
def listar_lotes_de_producto(producto_id: int, db: Session = Depends(get_db)):
    """Lotes ordenados FIFO (mas antiguo primero) para un producto dado."""
    return (
        db.query(LoteInventario)
        .filter(LoteInventario.producto_id == producto_id)
        .order_by(LoteInventario.fecha_ingreso.asc())
        .all()
    )
