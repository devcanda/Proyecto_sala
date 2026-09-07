"""
routers/alert_router.py
--------------------------
Semaforizacion de vencimientos: reciclado de la logica del proyecto
anterior del desarrollador (SEMED), adaptada a lotes de inventario.

Regla de negocio (umbrales por defecto, configurables via query params):
- ROJO:     vence en <= 3 dias (o ya vencio).
- AMARILLO: vence en <= 10 dias.
- VERDE:    todo lo demas.

Este endpoint es lo que alimenta el dashboard principal.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from backend.database import get_db
from backend.models.inventory import LoteInventario
from backend import schemas

router = APIRouter(prefix="/alertas", tags=["Alertas"])

UMBRAL_ROJO_DEFAULT = 3
UMBRAL_AMARILLO_DEFAULT = 10


def _nivel(dias_restantes: int, umbral_rojo: int, umbral_amarillo: int) -> str:
    if dias_restantes <= umbral_rojo:
        return "rojo"
    if dias_restantes <= umbral_amarillo:
        return "amarillo"
    return "verde"


@router.get("/vencimientos", response_model=list[schemas.LoteAlerta])
def semaforo_vencimientos(
    umbral_rojo_dias: int = Query(UMBRAL_ROJO_DEFAULT, ge=0),
    umbral_amarillo_dias: int = Query(UMBRAL_AMARILLO_DEFAULT, ge=0),
    solo_alertas: bool = Query(
        True, description="Si es True, omite lotes en nivel 'verde' (los que aun no requieren atencion)."
    ),
    db: Session = Depends(get_db),
):
    """
    Devuelve los lotes con existencia > 0 y fecha_vencimiento definida,
    clasificados por semaforo, ordenados del mas urgente al menos urgente.
    """
    hoy = datetime.now(timezone.utc)

    lotes = (
        db.query(LoteInventario)
        .options(joinedload(LoteInventario.producto))
        .filter(LoteInventario.cantidad_actual > 0)
        .filter(LoteInventario.fecha_vencimiento.isnot(None))
        .order_by(LoteInventario.fecha_vencimiento.asc())
        .all()
    )

    resultado: list[schemas.LoteAlerta] = []
    for lote in lotes:
        vencimiento = lote.fecha_vencimiento
        if vencimiento.tzinfo is None:
            vencimiento = vencimiento.replace(tzinfo=timezone.utc)
        dias_restantes = (vencimiento - hoy).days
        nivel = _nivel(dias_restantes, umbral_rojo_dias, umbral_amarillo_dias)

        if solo_alertas and nivel == "verde":
            continue

        resultado.append(
            schemas.LoteAlerta(
                id=lote.id,
                producto_id=lote.producto_id,
                producto_nombre=lote.producto.nombre if lote.producto else "(desconocido)",
                cantidad_actual=lote.cantidad_actual,
                costo_adquisicion=lote.costo_adquisicion,
                fecha_ingreso=lote.fecha_ingreso,
                fecha_vencimiento=lote.fecha_vencimiento,
                dias_restantes=dias_restantes,
                nivel=nivel,
            )
        )

    return resultado
