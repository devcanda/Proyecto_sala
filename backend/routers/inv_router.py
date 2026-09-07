"""
routers/inv_router.py
-----------------------
Endpoints de catalogo (productos) e inventario (lotes).

La logica de descuento de stock al vender vive en services/ (FIFO +
escandallos), no aqui: este router solo expone altas/consultas basicas de
catalogo e ingreso de mercancia.
"""
import io

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from PIL import Image, ImageOps
from sqlalchemy.orm import Session, selectinload

from backend.database import get_db, DATA_DIR
from backend.models.inventory import Producto, LoteInventario, RecetaIngrediente, Proveedor, NotaProducto
from backend import schemas

router = APIRouter(prefix="/inventario", tags=["Inventario"])

IMAGENES_DIR = DATA_DIR / "imagenes_productos"
IMAGENES_DIR.mkdir(exist_ok=True)
TAMANO_IMAGEN_PRODUCTO = (400, 400)


@router.get("/productos", response_model=list[schemas.ProductoOut])
def listar_productos(solo_activos: bool = True, db: Session = Depends(get_db)):
    # selectinload: Producto.stock_total (property en el modelo) recorre
    # producto.lotes; sin esto, serializar la lista dispara una consulta
    # de lotes POR CADA producto (N+1) cada vez que se carga el listado,
    # que es la ruta compartida por Retail, Hospitalidad, Productos e
    # Inventario. Con selectinload queda en 2 consultas sin importar
    # cuantos productos haya.
    query = db.query(Producto).options(selectinload(Producto.lotes))
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


@router.put("/productos/{producto_id}", response_model=schemas.ProductoOut)
def editar_producto(producto_id: int, payload: schemas.ProductoUpdate, db: Session = Depends(get_db)):
    producto = db.get(Producto, producto_id)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    datos = payload.model_dump(exclude_unset=True)
    if "codigo_barras" in datos and datos["codigo_barras"]:
        existente = (
            db.query(Producto)
            .filter(Producto.codigo_barras == datos["codigo_barras"], Producto.id != producto_id)
            .first()
        )
        if existente:
            raise HTTPException(status_code=409, detail="Ya existe un producto con ese codigo de barras")

    for campo, valor in datos.items():
        setattr(producto, campo, valor)

    db.commit()
    db.refresh(producto)
    return producto


@router.post("/productos/{producto_id}/imagen", response_model=schemas.ProductoOut)
async def subir_imagen_producto(
    producto_id: int, archivo: UploadFile = File(...), db: Session = Depends(get_db)
):
    """
    Ajusta cualquier imagen (sin importar tamaño/proporcion original) a un
    cuadrado fijo de TAMANO_IMAGEN_PRODUCTO recortando el sobrante
    (ImageOps.fit), para que la grilla de productos se vea uniforme.
    """
    producto = db.get(Producto, producto_id)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    contenido = await archivo.read()
    try:
        imagen = Image.open(io.BytesIO(contenido))
        imagen = imagen.convert("RGB")
    except Exception as exc:
        raise HTTPException(status_code=422, detail="El archivo no es una imagen valida") from exc

    imagen = ImageOps.fit(imagen, TAMANO_IMAGEN_PRODUCTO, Image.LANCZOS)
    nombre_archivo = f"{producto_id}.jpg"
    imagen.save(IMAGENES_DIR / nombre_archivo, "JPEG", quality=85)

    producto.imagen = nombre_archivo
    db.commit()
    db.refresh(producto)
    return producto


@router.get("/proveedores", response_model=list[schemas.ProveedorOut])
def listar_proveedores(db: Session = Depends(get_db)):
    return db.query(Proveedor).order_by(Proveedor.nombre).all()


@router.post("/proveedores", response_model=schemas.ProveedorOut, status_code=201)
def crear_proveedor(payload: schemas.ProveedorCreate, db: Session = Depends(get_db)):
    proveedor = Proveedor(nombre=payload.nombre)
    db.add(proveedor)
    db.commit()
    db.refresh(proveedor)
    return proveedor


@router.get("/productos/{producto_id}/notas", response_model=list[schemas.NotaProductoOut])
def listar_notas_de_producto(producto_id: int, db: Session = Depends(get_db)):
    return (
        db.query(NotaProducto)
        .filter(NotaProducto.producto_id == producto_id)
        .order_by(NotaProducto.creado_en.desc())
        .all()
    )


@router.post("/productos/{producto_id}/notas", response_model=schemas.NotaProductoOut, status_code=201)
def agregar_nota_producto(
    producto_id: int, payload: schemas.NotaProductoCreate, db: Session = Depends(get_db)
):
    producto = db.get(Producto, producto_id)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    nota = NotaProducto(producto_id=producto_id, texto=payload.texto)
    db.add(nota)
    db.commit()
    db.refresh(nota)
    return nota


@router.delete("/notas/{nota_id}", status_code=204)
def eliminar_nota_producto(nota_id: int, db: Session = Depends(get_db)):
    nota = db.get(NotaProducto, nota_id)
    if not nota:
        raise HTTPException(status_code=404, detail="Nota no encontrada")
    db.delete(nota)
    db.commit()


@router.get("/productos/{producto_id}/receta", response_model=list[schemas.RecetaIngredienteOut])
def listar_receta(producto_id: int, db: Session = Depends(get_db)):
    ingredientes = (
        db.query(RecetaIngrediente)
        .filter(RecetaIngrediente.producto_compuesto_id == producto_id)
        .all()
    )
    return [
        schemas.RecetaIngredienteOut(
            id=i.id,
            producto_compuesto_id=i.producto_compuesto_id,
            insumo_id=i.insumo_id,
            cantidad_requerida=i.cantidad_requerida,
            insumo_nombre=i.insumo.nombre if i.insumo else "(desconocido)",
        )
        for i in ingredientes
    ]


@router.post("/productos/{producto_id}/receta", response_model=schemas.RecetaIngredienteOut, status_code=201)
def agregar_ingrediente_receta(
    producto_id: int, payload: schemas.RecetaIngredienteCreate, db: Session = Depends(get_db)
):
    producto = db.get(Producto, producto_id)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    insumo = db.get(Producto, payload.insumo_id)
    if not insumo:
        raise HTTPException(status_code=404, detail="Insumo no encontrado")

    ingrediente = RecetaIngrediente(
        producto_compuesto_id=producto_id,
        insumo_id=payload.insumo_id,
        cantidad_requerida=payload.cantidad_requerida,
    )
    db.add(ingrediente)
    db.commit()
    db.refresh(ingrediente)
    return schemas.RecetaIngredienteOut(
        id=ingrediente.id,
        producto_compuesto_id=ingrediente.producto_compuesto_id,
        insumo_id=ingrediente.insumo_id,
        cantidad_requerida=ingrediente.cantidad_requerida,
        insumo_nombre=insumo.nombre,
    )


@router.delete("/recetas/{ingrediente_id}", status_code=204)
def eliminar_ingrediente_receta(ingrediente_id: int, db: Session = Depends(get_db)):
    ingrediente = db.get(RecetaIngrediente, ingrediente_id)
    if not ingrediente:
        raise HTTPException(status_code=404, detail="Ingrediente de receta no encontrado")
    db.delete(ingrediente)
    db.commit()


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


@router.put("/lotes/{lote_id}", response_model=schemas.LoteInventarioOut)
def editar_lote(lote_id: int, payload: schemas.LoteInventarioUpdate, db: Session = Depends(get_db)):
    """
    Correccion manual de un lote ya existente (ej. tras un conteo fisico
    o un error de captura al registrarlo). No crea movimiento nuevo: pisa
    los valores del lote indicado.
    """
    lote = db.get(LoteInventario, lote_id)
    if not lote:
        raise HTTPException(status_code=404, detail="Lote no encontrado")

    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(lote, campo, valor)

    db.commit()
    db.refresh(lote)
    return lote
