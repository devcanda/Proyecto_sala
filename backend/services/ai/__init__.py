"""
services/ai
------------
Carpeta reservada para los modulos predictivos mencionados en la vision del
proyecto (documento maestro, seccion 2 y 5-A): prediccion de demanda,
sugerencia de puntos de reorden, deteccion de anomalias en ventas, etc.

Se deja vacia intencionalmente en esta fase. El esquema de base de datos
(lotes_inventario con fecha_ingreso/fecha_vencimiento/costo_adquisicion,
orden_detalles con cantidad y precio historico) ya provee las series de
tiempo necesarias para entrenar estos modelos sin migraciones futuras.
"""
