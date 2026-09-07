"""
models/config.py
------------------
Configuracion general del negocio: no es catalogo de venta ni inventario,
por eso vive en un modulo aparte de inventory.py/pos.py.

`ConfiguracionNegocio` es un singleton (una sola fila, id=1 siempre):
datos basicos del negocio, pensados para cuando el Modulo Contable
necesite emitir facturas/reportes (fase posterior).

`Impresora` es un catalogo simple de nombres de impresora_destino, para
que el formulario de productos ofrezca un selector en vez de texto libre
(evita typos como "Barra" vs "barra" vs "BARRA" que romperian el ruteo
de comandas en Hospitalidad).
"""
from sqlalchemy import Column, Integer, String

from backend.database import Base


class ConfiguracionNegocio(Base):
    __tablename__ = "configuracion_negocio"

    id = Column(Integer, primary_key=True, default=1)
    nombre_negocio = Column(String(150), nullable=True)
    nit = Column(String(50), nullable=True)
    direccion = Column(String(200), nullable=True)
    telefono = Column(String(50), nullable=True)


class Impresora(Base):
    __tablename__ = "impresoras"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(50), nullable=False, unique=True)
