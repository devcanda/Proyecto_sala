"""
services/hardware/printing.py
--------------------------------
Abstraccion de impresion termica de bajo nivel usando python-escpos.

Objetivo del modulo (ver documento maestro, seccion 3 - Hospitalidad):
rutear comandas a impresoras especificas segun el `impresora_destino` del
producto (ej. "barra" para tragos, "cocina" para platos), ademas de abrir
el cajon monedero al cerrar una venta en efectivo.

Este archivo es deliberadamente un esqueleto: la conexion real depende del
hardware presente en cada sitio (USB, red, o serial), que se configurara
por punto de venta. Se deja la interfaz lista para que main.py / pos_router
la puedan invocar sin acoplarse a una marca de impresora concreta.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

try:
    from escpos.printer import Usb, Network  # type: ignore
except ImportError:  # pragma: no cover - escpos es opcional en entornos sin hardware
    Usb = None  # type: ignore
    Network = None  # type: ignore


@dataclass
class ImpresoraConfig:
    """Configuracion de una impresora fisica, identificada por un alias logico."""
    alias: str  # ej. "barra", "cocina", "caja"
    tipo: str  # "usb" | "network"
    # USB:
    vendor_id: Optional[int] = None
    product_id: Optional[int] = None
    # Network:
    host: Optional[str] = None
    puerto: int = 9100


class GestorImpresion:
    """
    Punto de entrada unico para imprimir. Mantiene un registro de impresoras
    configuradas por alias (ej. "barra", "cocina") y rutea cada comanda a
    la que corresponda segun `Producto.impresora_destino`.

    TODO (fase de hardware real): cargar `ImpresoraConfig` desde variables
    de entorno o un archivo de configuracion por punto de venta, y probar
    conexion/errores de impresora fisica desconectada.
    """

    def __init__(self):
        self._impresoras: dict[str, ImpresoraConfig] = {}

    def registrar(self, config: ImpresoraConfig) -> None:
        self._impresoras[config.alias] = config

    def _conectar(self, alias: str):
        if Usb is None:
            raise RuntimeError(
                "python-escpos no esta instalado. Ejecuta 'pip install -r requirements.txt'."
            )
        config = self._impresoras.get(alias)
        if not config:
            raise ValueError(f"No hay impresora configurada con alias '{alias}'")

        if config.tipo == "usb":
            return Usb(config.vendor_id, config.product_id)
        if config.tipo == "network":
            return Network(config.host, port=config.puerto)
        raise ValueError(f"Tipo de impresora desconocido: {config.tipo}")

    def imprimir_comanda(self, alias: str, lineas: list[str]) -> None:
        printer = self._conectar(alias)
        printer.set(align="left")
        for linea in lineas:
            printer.text(linea + "\n")
        printer.cut()

    def abrir_cajon(self, alias: str = "caja") -> None:
        printer = self._conectar(alias)
        printer.cashdraw(2)


# Instancia compartida por la app. Se registra/configura en el startup de main.py.
gestor_impresion = GestorImpresion()
