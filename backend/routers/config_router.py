"""
routers/config_router.py
--------------------------
Configuracion general del negocio: datos basicos (singleton) y catalogo
de impresoras usado por el selector del formulario de productos.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.config import ConfiguracionNegocio, Impresora
from backend import schemas

router = APIRouter(prefix="/config", tags=["Configuracion"])


@router.get("/negocio", response_model=schemas.ConfiguracionNegocioOut)
def obtener_configuracion_negocio(db: Session = Depends(get_db)):
    config = db.get(ConfiguracionNegocio, 1)
    if not config:
        # Primera vez que se pide: se crea la fila singleton vacia.
        config = ConfiguracionNegocio(id=1)
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


@router.put("/negocio", response_model=schemas.ConfiguracionNegocioOut)
def actualizar_configuracion_negocio(
    payload: schemas.ConfiguracionNegocioUpdate, db: Session = Depends(get_db)
):
    config = db.get(ConfiguracionNegocio, 1)
    if not config:
        config = ConfiguracionNegocio(id=1)
        db.add(config)

    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(config, campo, valor)

    db.commit()
    db.refresh(config)
    return config


@router.get("/impresoras", response_model=list[schemas.ImpresoraOut])
def listar_impresoras(db: Session = Depends(get_db)):
    return db.query(Impresora).order_by(Impresora.nombre).all()


@router.post("/impresoras", response_model=schemas.ImpresoraOut, status_code=201)
def crear_impresora(payload: schemas.ImpresoraCreate, db: Session = Depends(get_db)):
    existente = db.query(Impresora).filter(Impresora.nombre == payload.nombre).first()
    if existente:
        raise HTTPException(status_code=409, detail="Ya existe una impresora con ese nombre")

    impresora = Impresora(nombre=payload.nombre)
    db.add(impresora)
    db.commit()
    db.refresh(impresora)
    return impresora


@router.delete("/impresoras/{impresora_id}", status_code=204)
def eliminar_impresora(impresora_id: int, db: Session = Depends(get_db)):
    impresora = db.get(Impresora, impresora_id)
    if not impresora:
        raise HTTPException(status_code=404, detail="Impresora no encontrada")
    db.delete(impresora)
    db.commit()
