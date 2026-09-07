"""
main.py
--------
Entrypoint de la aplicacion FastAPI.

En desarrollo (modo Standalone/SQLite) crea las tablas automaticamente al
arrancar. En produccion, y especialmente en modo Red LAN/PostgreSQL, esto
deberia reemplazarse por migraciones versionadas (ej. Alembic) para no
perder control sobre cambios de esquema entre cajas ya desplegadas.
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.database import Base, engine
import backend.models  # noqa: F401  (registra los modelos en Base.metadata)
from backend.routers import pos_router, inv_router, alert_router, config_router
from backend.routers.inv_router import IMAGENES_DIR

app = FastAPI(
    title="Salsa POS",
    description="Sistema POS, Inventario y Contabilidad Local-First (retail + hospitalidad).",
    version="0.1.0",
)

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:1420")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pos_router.router)
app.include_router(inv_router.router)
app.include_router(alert_router.router)
app.include_router(config_router.router)

# Imagenes de producto (POST /inventario/productos/{id}/imagen las guarda aqui).
app.mount("/media", StaticFiles(directory=IMAGENES_DIR), name="media")


@app.on_event("startup")
def on_startup():
    # DEV ONLY: ver docstring del modulo. En modo postgresql/produccion,
    # sustituir por `alembic upgrade head`.
    Base.metadata.create_all(bind=engine)


@app.get("/", tags=["Salud"])
def salud():
    return {"status": "ok", "servicio": "salsa-pos-backend"}
