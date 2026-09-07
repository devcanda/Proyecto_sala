# Salsa POS

Sistema propio de Punto de Venta (POS), Inventario y Contabilidad para
salsamentarias, minimarkets, restaurantes, bares y licoreras. Se despliega
en dos modalidades **independientes**, elegidas por negocio según su
conectividad:

- **Local:** SQLite en una sola máquina, sin ninguna dependencia de
  internet. Pensado para negocios con conexión intermitente o nula.
- **Nube:** el mismo backend contenerizado corriendo como servicio en AWS o
  Azure, contra una base de datos administrada (RDS / Azure Database for
  PostgreSQL). Pensado para negocios con conectividad estable que prefieren
  no mantener un servidor propio.

No hay sincronización entre ambos modos ni cambio automático de uno a otro:
cada instalación queda fija en el modo que se eligió al desplegarla.

> Este README es la **bitácora principal** del proyecto. Cada decisión
> arquitectónica, cambio de esquema de base de datos o pieza de lógica de
> negocio relevante debe quedar registrada aquí, en orden cronológico dentro
> de la sección [Bitácora de decisiones](#8-bitácora-de-decisiones).

## Índice
1. [Visión y referencia](#1-visión-y-referencia)
2. [Casos de uso](#2-casos-de-uso)
3. [Stack tecnológico](#3-stack-tecnológico)
4. [Estructura del repositorio](#4-estructura-del-repositorio)
5. [Esquema de base de datos](#5-esquema-de-base-de-datos)
6. [Lógica de negocio implementada](#6-lógica-de-negocio-implementada)
7. [Cómo correr el proyecto](#7-cómo-correr-el-proyecto)
8. [Bitácora de decisiones](#8-bitácora-de-decisiones)
9. [Backlog / próximas fases](#9-backlog--próximas-fases)

---

## 1. Visión y referencia

Inspirado en la limpieza de interfaz y agilidad operativa de
[Aronium](https://www.aronium.com/en), pero con tres diferencias
deliberadas:

- **100% modificable**: sin licencias ni cajas negras.
- **Preparado para IA desde el día cero**: el esquema de base de datos
  guarda las series de tiempo (ventas, costos, vencimientos) necesarias
  para modelos predictivos de demanda, sin necesitar migraciones futuras.
- **Módulo contable nativo** (fase posterior): cada lote y cada línea de
  venta ya registran costo y precio histórico, dejando lista la base para
  utilidad bruta y asientos de doble entrada.

## 2. Casos de uso

El sistema es modular para dos ecosistemas comerciales:

| Ecosistema | Necesidades clave |
|---|---|
| **Retail** (salsamentarias, minimarkets) | Venta ultra rápida, productos por peso y por unidad, lector de barras emulando teclado |
| **Hospitalidad** (restaurantes, bares, licoreras) | Cuentas abiertas por mesa, ruteo de impresión (barra/cocina), productos compuestos ("escandallos") |

El modo activo (`retail` / `hospitalidad`) se elige desde la barra superior
del frontend y se persiste en `localStorage`; ambos modos comparten el
mismo backend y catálogo de productos.

## 3. Stack tecnológico

- **Backend:** Python + [FastAPI](https://fastapi.tiangolo.com/), asíncrono,
  tipado con Pydantic.
- **Frontend:** HTML/CSS/JS vanilla, pensado para empaquetarse como
  aplicación de escritorio con Tauri o Electron.
- **Base de datos:**
  - *Modo Standalone* (local, 1 PC, sin internet): SQLite (`backend/data/*.db`).
  - *Modo Servidor* (`DB_MODE=postgresql`): PostgreSQL, con dos variantes
    posibles según dónde corra ese Postgres:
    - **LAN local:** contenedor Docker orquestado vía Portainer, dentro de
      la red del negocio (ver [docker-compose.yml](docker-compose.yml)).
    - **Nube:** AWS RDS o Azure Database for PostgreSQL, con el backend
      desplegado en AWS ECS Fargate o Azure Container Apps (ver guía en la
      sección [Cómo correr el proyecto](#7-cómo-correr-el-proyecto)).
  - El cambio entre modos es solo variables de entorno (`DB_MODE`,
    `POSTGRES_*`), ver [backend/database.py](backend/database.py). El
    código de la aplicación es idéntico en los tres casos.
- **Hardware:** [`python-escpos`](https://python-escpos.readthedocs.io/)
  para impresoras térmicas y apertura de cajón monedero
  (`backend/services/hardware/printing.py`).

## 4. Estructura del repositorio

```text
├── backend/
│   ├── main.py                     # Entrypoint FastAPI, CORS, startup
│   ├── database.py                 # Conexión SQLAlchemy (SQLite/PostgreSQL)
│   ├── schemas.py                   # DTOs Pydantic (contrato de la API)
│   ├── models/
│   │   ├── inventory.py             # Producto, Proveedor, NotaProducto, RecetaIngrediente, LoteInventario
│   │   ├── pos.py                   # Mesa, Orden, OrdenDetalle
│   │   └── config.py                 # ConfiguracionNegocio, Impresora
│   ├── routers/
│   │   ├── pos_router.py            # Ordenes, mesas, cobro
│   │   ├── inv_router.py            # Catálogo, lotes, proveedores, notas, imagen de producto
│   │   ├── alert_router.py          # Semaforización de vencimientos
│   │   └── config_router.py          # Datos del negocio, impresoras
│   ├── services/
│   │   ├── ventas.py                 # FIFO + expansión de escandallos (salta si es_servicio)
│   │   ├── hardware/printing.py      # Impresión térmica / cajón monedero
│   │   └── ai/                       # Reservado para modelos predictivos
│   └── data/
│       ├── *.db                      # SQLite (ignorado por git)
│       └── imagenes_productos/       # Imagenes subidas, servidas en /media (ignorado por git)
├── frontend/
│   ├── index.html                    # Shell: sidebar (Venta / Administración > submenú) + input de barras
│   ├── views/
│   │   ├── pos_retail.html           # Venta > Retail: estilo Aronium (ticket + panel de acciones + grilla)
│   │   ├── pos_hospitalidad.html     # Venta > Hospitalidad: mapa de mesas + cuenta
│   │   ├── productos.html            # Administración > Productos: formulario completo + receta + notas
│   │   ├── inventario.html           # Administración > Inventario: lotes por producto + alta de lote
│   │   ├── alertas.html              # Administración > Alertas: semaforo de vencimientos
│   │   └── configuracion.html        # Administración > Configuración: negocio, impresoras, proveedores
│   ├── css/style.css
│   └── js/
│       ├── api.js                    # Cliente fetch hacia el backend
│       ├── barcode.js                # Foco persistente + multiplicadores (5*codigo)
│       └── app.js                    # Orquestador: ruteo de vistas y estado
├── docker-compose.yml                 # Modo Servidor, variante LAN local (Postgres + backend)
├── Dockerfile                          # Imagen del backend
├── requirements.txt
├── .env.example
└── README.md                           # Esta bitácora
```

## 5. Esquema de base de datos

Definido en `backend/models/`. Resumen de tablas y su porqué:

| Tabla | Campos clave | Notas |
|---|---|---|
| `productos` | `codigo_barras`, `codigo` (SKU manual), `tipo` (`unidad`/`peso`/`compuesto`), `unidad_medida`, `precio_venta`, `costo`, `incluye_impuesto`, `grupo`, `descripcion`, `es_servicio`, `proveedor_id`, `stock_bajo_activo`/`stock_bajo_umbral`, `imagen`, `impresora_destino` | Catálogo central; `grupo` es texto libre (no una tabla aparte, antes se llamaba `categoria`) para filtrar la grilla de Retail; `es_servicio=True` salta el descuento de inventario al vender (`services/ventas.py`); `imagen` solo se llena vía `POST /inventario/productos/{id}/imagen`, nunca por create/update directo |
| `proveedores` | `nombre` | Catálogo mínimo, gestionado en Configuración |
| `notas_producto` | `producto_id`, `texto`, `creado_en` | Notas libres agregables/eliminables por producto |
| `recetas_ingredientes` | `producto_compuesto_id`, `insumo_id`, `cantidad_requerida` | Tabla pivote de escandallos (ej. 1 Mojito = 50ml ron + azúcar + limón + 1 vaso) |
| `lotes_inventario` | `producto_id`, `cantidad_actual`, `costo_adquisicion`, `fecha_ingreso`, `fecha_vencimiento` | Existencias físicas por lote, base del FIFO y de la semaforización |
| `mesas` | `nombre`, `estado` (`libre`/`ocupada`/`reservada`) | Solo aplica en modo Hospitalidad |
| `ordenes` | `tipo_orden` (`directa`/`mesa`), `mesa_id`, `estado` (`abierta`/`pagada`/`cancelada`) | Cabecera del ticket o cuenta |
| `orden_detalles` | `cantidad` (decimal, admite gramos), `precio_unitario_historico` | Precio congelado al momento de la venta: base del futuro cálculo de utilidad bruta |
| `configuracion_negocio` | `nombre_negocio`, `nit`, `direccion`, `telefono` | Singleton (una sola fila, id=1) |
| `impresoras` | `nombre` | Catálogo mínimo, alimenta el selector "Impresora destino" de Productos |

**Relación con el Módulo Contable (fase posterior):** cada `LoteInventario`
guarda su `costo_adquisicion` y cada `OrdenDetalle` guarda su
`precio_unitario_historico`. La utilidad bruta de una línea de venta es,
en su forma más simple, `precio_unitario_historico - costo_adquisicion` del
lote efectivamente consumido. El esquema ya soporta esto sin cambios
futuros; falta implementar el módulo de asientos de doble entrada.

## 6. Lógica de negocio implementada

### A. FIFO + Escandallos (`backend/services/ventas.py`)
Punto único de descuento de inventario al vender (`descontar_inventario_por_venta`):

- Si el producto es simple (`unidad`/`peso`): descuenta del lote con
  `fecha_ingreso` más antigua que aún tenga existencia, pasando al
  siguiente lote si no alcanza (FIFO real, no solo orden de lectura).
- Si el producto es `compuesto` (escandallo): expande recursivamente su
  receta (`recetas_ingredientes`) y aplica la misma regla FIFO sobre cada
  insumo, multiplicando `cantidad_requerida` por la cantidad vendida.
- Si no hay stock suficiente, lanza `StockInsuficienteError`, que
  `pos_router.py` traduce a un `409 Conflict` con el detalle de cuánto
  falta.

Verificado con una prueba funcional end-to-end (creación de insumo, lote
con vencimiento, producto compuesto, venta que descuenta el insumo
correctamente, y venta que excede stock devolviendo 409).

### B. Semaforización de vencimientos (`backend/routers/alert_router.py`)
Reciclaje de la lógica del proyecto anterior del desarrollador (SEMED),
adaptada a lotes de inventario. Clasifica cada lote con existencia y fecha
de vencimiento en tres niveles según días restantes:

- **Rojo:** vence en ≤ 3 días (umbral configurable vía query param).
- **Amarillo:** vence en ≤ 10 días.
- **Verde:** todo lo demás (se omite del resultado por defecto).

Endpoint: `GET /alertas/vencimientos`, pensado para alimentar el dashboard.

### C. Foco persistente para lector de código de barras (`frontend/js/barcode.js`)
El campo `#barcode-input` recupera el foco automáticamente tras cualquier
clic fuera de él (y en un intervalo de respaldo), para que el operario
nunca necesite tocar el mouse. Soporta el formato de multiplicador rápido
`5*codigo_de_barras` para agregar 5 unidades de una sola pasada.

### D. Flujo de mesas (Hospitalidad)
`GET /pos/mesas/{id}/orden-abierta` permite retomar la cuenta abierta de
una mesa ya ocupada en vez de crear una nueva orden duplicada; al pagar
(`POST /pos/ordenes/{id}/pagar`) la mesa vuelve a estado `libre`. Las mesas
se crean desde la propia grilla de Hospitalidad (tarjeta "+ Nueva mesa"),
vía `POST /pos/mesas`.

### E. Navegación por secciones (`frontend/js/app.js`, `frontend/index.html`)
El shell usa una barra lateral (inspirada en Aronium) con 4 secciones:
**Venta** (la pantalla de caja, con su propio sub-modo Retail/Hospitalidad
tal como ya existía), **Productos** (catálogo + editor de receta de
escandallos), **Inventario** (lotes por producto + alta de lote) y
**Alertas** (semáforo de vencimientos a pantalla completa). Cambiar de
sección nunca resetea una venta en curso (`state.ordenActual`); solo
cambiar de sub-modo Retail↔Hospitalidad lo hace, como antes.

**Gotcha de CSS encontrado y corregido:** un elemento con el atributo
`hidden` deja de ocultarse si CUALQUIER regla de tu propio stylesheet le
fija `display` (ej. `.mi-clase { display: flex }`), sin importar
especificidad — el origen "autor" de la cascada le gana siempre al
"user-agent" que trae `[hidden] { display: none }`. Esto rompía
silenciosamente la grilla de mesas (`.pos-hospitalidad__cuenta` se veía
siempre superpuesta) y el sub-menú Retail/Hospitalidad (seguía visible en
Productos/Inventario/Alertas). Se corrigió agregando `:not([hidden])` a
esos selectores (`.topbar`, `.form-inline`, `.pos-hospitalidad__cuenta`)
en `frontend/css/style.css`.

## 7. Cómo correr el proyecto

### Backend (modo Standalone / SQLite — recomendado para desarrollo y para 1 sola caja)
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # dejar DB_MODE=sqlite
uvicorn backend.main:app --reload
```
La API queda en `http://127.0.0.1:8000` (docs interactivos en `/docs`).
Las tablas se crean automáticamente al arrancar (ver nota en
`backend/main.py` sobre reemplazar esto por migraciones en producción).

### Backend (modo Servidor / PostgreSQL — variante LAN local)
```bash
cp .env.example .env               # completar POSTGRES_* con credenciales reales
docker compose up -d --build
```

### Backend (modo Servidor / PostgreSQL — variante Nube en AWS)
Requiere una cuenta de AWS propia y `aws` CLI configurado; genera costos en
la cuenta del cliente/desarrollador.

1. **Base de datos administrada (RDS):**
   ```bash
   aws rds create-db-instance \
     --db-instance-identifier salsa-pos-db \
     --db-instance-class db.t3.micro \
     --engine postgres \
     --master-username salsa_pos \
     --master-user-password "<clave-segura>" \
     --allocated-storage 20 \
     --publicly-accessible false
   ```
   Anotar el endpoint que devuelve (`--db-instance-identifier` una vez
   disponible, vía `aws rds describe-db-instances`).

2. **Imagen del backend (ECR):**
   ```bash
   aws ecr create-repository --repository-name salsa-pos-backend
   aws ecr get-login-password | docker login --username AWS --password-stdin <account-id>.dkr.ecr.<region>.amazonaws.com
   docker build -t <account-id>.dkr.ecr.<region>.amazonaws.com/salsa-pos-backend:latest .
   docker push <account-id>.dkr.ecr.<region>.amazonaws.com/salsa-pos-backend:latest
   ```

3. **Servicio (ECS Fargate):** crear un cluster ECS, una task definition
   que use la imagen anterior con las variables de entorno `DB_MODE=postgresql`,
   `POSTGRES_HOST=<endpoint-rds>`, `POSTGRES_SSLMODE=require` y el resto de
   `POSTGRES_*`, y un servicio Fargate detrás de un Application Load
   Balancer para exponer el puerto 8000 con HTTPS.

### Backend (modo Servidor / PostgreSQL — variante Nube en Azure)
Requiere una cuenta de Azure propia y `az` CLI configurado; genera costos
en la cuenta del cliente/desarrollador.

1. **Base de datos administrada:**
   ```bash
   az postgres flexible-server create \
     --name salsa-pos-db \
     --resource-group <grupo-recursos> \
     --admin-user salsa_pos \
     --admin-password "<clave-segura>" \
     --sku-name Standard_B1ms \
     --public-access none
   ```

2. **Imagen del backend (Azure Container Registry):**
   ```bash
   az acr create --name salsapos --resource-group <grupo-recursos> --sku Basic
   az acr build --registry salsapos --image salsa-pos-backend:latest .
   ```

3. **Servicio (Azure Container Apps):**
   ```bash
   az containerapp create \
     --name salsa-pos-backend \
     --resource-group <grupo-recursos> \
     --image salsapos.azurecr.io/salsa-pos-backend:latest \
     --target-port 8000 --ingress external \
     --env-vars DB_MODE=postgresql POSTGRES_HOST=<host-flexible-server> POSTGRES_SSLMODE=require ...
   ```

En ambos proveedores, las credenciales (`POSTGRES_PASSWORD`, etc.) deben
inyectarse como secretos administrados (AWS Secrets Manager / Azure Key
Vault) en un despliegue real, no como variables de entorno en texto plano;
aquí se muestran así solo para simplificar la guía inicial.

### Frontend
El frontend carga sus vistas (`views/*.html`) vía `fetch`, por lo que debe
servirse por HTTP, no abrirse como archivo local:
```bash
npx http-server frontend -p 5173
```
Luego abrir `http://127.0.0.1:5173`. El empaquetado final como app de
escritorio instalable (Tauri/Electron) queda pendiente para una fase
posterior (ver Backlog).

## 8. Bitácora de decisiones

### 2026-09-07 — Andamiaje inicial del proyecto
- Se crea la estructura completa de directorios descrita en el documento
  maestro (`backend/`, `frontend/`).
- Se implementa el esquema de base de datos completo de la sección "Core"
  (productos, recetas_ingredientes, lotes_inventario, mesas, ordenes,
  orden_detalles) vía SQLAlchemy, con soporte dual SQLite/PostgreSQL
  seleccionable por variable de entorno `DB_MODE`.
- Se implementa la lógica de descuento de inventario FIFO + expansión de
  escandallos (`services/ventas.py`), verificada con una prueba funcional
  end-to-end (ver sección 6-A).
- Se implementa la semaforización de vencimientos como endpoint de
  alertas, reciclando la lógica conceptual del proyecto SEMED del
  desarrollador.
- Se agrega un endpoint no listado explícitamente en el documento maestro
  pero necesario para el flujo de mesas: `GET /pos/mesas/{id}/orden-abierta`,
  para poder retomar una cuenta abierta al reseleccionar una mesa ocupada
  desde el frontend.
- Se deja el módulo `services/hardware/printing.py` como esqueleto
  funcional (interfaz lista, conexión real a impresoras pendiente de
  hardware físico por sitio) y `services/ai/` vacío pero documentado como
  reservado.
- Se agrega `docker-compose.yml` + `Dockerfile` para el modo Red LAN,
  aprovechando la experiencia del desarrollador en Docker/Portainer.
- Se valida sintaxis y comportamiento en runtime del backend completo
  (instalación de dependencias en un entorno virtual temporal, arranque de
  la app, y prueba funcional de los flujos de Retail, Hospitalidad,
  escandallos y semaforización) antes de dar el andamiaje por cerrado.

### 2026-09-07 — Definición de modos de despliegue: Local vs Nube
- El cliente objetivo (salsamentaria) tiene conectividad intermitente, pero
  el desarrollador quiere ofrecer también una variante en la nube (AWS o
  Azure) para negocios con internet estable. Se decidió explícitamente que
  ambos modos son **despliegues independientes** por instalación (no hay
  sincronización local↔nube ni cambio automático entre ellos); esa
  alternativa (local con sync automático a la nube) se descartó por ahora
  por su complejidad (motor de sincronización + resolución de conflictos)
  y queda anotada en el Backlog por si se necesita más adelante.
- Se generalizó el ya existente `DB_MODE=postgresql` (antes documentado
  solo como "Red LAN") para cubrir también Postgres administrado en la
  nube: se agregó soporte de `POSTGRES_SSLMODE` en
  [backend/database.py](backend/database.py), ya que AWS RDS y Azure
  Database for PostgreSQL exigen SSL y un Postgres local en Docker
  normalmente no. No fue necesario ningún otro cambio de código: el mismo
  backend sirve para LAN local y para nube, solo cambia a qué host apunta.
- Se documentaron en el README guías paso a paso de despliegue en AWS
  (RDS + ECR + ECS Fargate) y Azure (Flexible Server + ACR + Container
  Apps). Son guías manuales de referencia, no scripts ejecutados ni
  probados contra una cuenta real (requieren credenciales propias del
  cliente/desarrollador); ver Backlog para automatizarlas.

### 2026-09-07 — Navegación real por secciones (estilo Aronium) + endpoints faltantes
- El frontend solo exponía la pantalla de venta: no había forma de crear
  productos, lotes, mesas ni ver alertas desde la UI (dos huecos eran
  bloqueos reales, no solo de UX: no existía `POST /pos/mesas` — por eso
  la grilla de Hospitalidad se veía rota/vacía en las capturas que trajo
  el desarrollador — ni ningún endpoint para definir recetas de
  escandallo). Se agregó, siguiendo el mismo patrón de los routers
  existentes: `POST /pos/mesas`, `PUT /inventario/productos/{id}`,
  `GET`/`POST /inventario/productos/{id}/receta` y
  `DELETE /inventario/recetas/{id}` (ver schemas nuevos en
  `backend/schemas.py`: `ProductoUpdate`, `RecetaIngredienteCreate/Out`,
  `MesaCreate`).
- El frontend se reestructuró a una barra lateral (Venta / Productos /
  Inventario / Alertas), inspirada explícitamente en Aronium a pedido del
  desarrollador, con 3 vistas nuevas (`productos.html`, `inventario.html`,
  `alertas.html`) y una tarjeta "+ Nueva mesa" en Hospitalidad. Ver detalle
  en la sección 6-E.
- Se encontró y corrigió un bug de CSS preexistente (no introducido en
  este cambio, pero que se manifestaba en el mismo flujo de mesas que el
  desarrollador reportó rota): reglas de `display` en `style.css` vencían
  al atributo `[hidden]` por reglas de cascada (autor > user-agent),
  dejando la cuenta de una mesa siempre visible encima de la grilla. Ver
  nota técnica en 6-E.
- Verificado de punta a punta con un navegador headless (Playwright,
  instalado ad-hoc en el scratchpad de la sesión, no committeado al
  repo): crear producto, editar producto compuesto y definirle receta,
  registrar lote y verlo en Alertas con su badge de color, crear mesa
  nueva y vender sobre ella. Cero errores de consola en las 4 secciones.

### 2026-09-07 — Buscador y categorías en la grilla de Retail
- A pedido explícito del desarrollador, se priorizó pulir primero la
  pantalla de Retail (por encima de Hospitalidad) con un buscador por
  nombre/código y filtro por categoría, ya que el catálogo real crecerá
  más allá de lo manejable en una grilla plana sin filtrar.
- Se agregó `categoria` a `productos` como texto libre (con autocompletado
  vía `<datalist>` en el formulario, para evitar categorías duplicadas por
  typos) en vez de una tabla `categorias` aparte, siguiendo el mismo
  patrón ya usado por `impresora_destino`: mantiene el esquema simple sin
  necesitar un CRUD propio de categorías.
- El buscador/filtro es client-side sobre `state.productos` (ya cargado
  en memoria), sin nuevo endpoint de búsqueda: el catálogo esperado para
  un solo negocio no justifica paginación ni búsqueda en el servidor.
- Deliberadamente **no** se tocó Hospitalidad en este cambio: la grilla de
  productos dentro de la cuenta de una mesa reutiliza la misma función de
  render, pero sigue mostrando el catálogo completo sin filtrar porque esa
  vista no tiene los controles de buscador/categoría (ver
  `frontend/js/app.js`, función `renderProductosGrid`).

### 2026-09-07 — Reskin oscuro + ticket como tabla (inspirado en la pantalla de venta de Aronium)
- El desarrollador compartió una captura de la pantalla de venta real de
  Aronium (tema oscuro, ticket como tabla con columnas Nombre/Cantidad/
  Precio/Total, panel lateral de acciones con atajos F2-F12, botones de
  método de pago, desglose Subtotal/Impuestos/Total) y pidió adaptarla
  "paso a paso". Se acordó como primer paso, de varios: tema oscuro +
  ticket como tabla, dejando el resto (panel de atajos, métodos de pago,
  impuestos) para pasos posteriores.
- Paleta oscura en `:root` (`frontend/css/style.css`). Nota para futuras
  ediciones: `--color-primary-dark` invirtió su rol tonal respecto al
  tema claro original (antes más oscuro que `--color-primary` para texto
  legible sobre blanco; ahora más claro, para texto legible sobre fondo
  oscuro) — se mantuvo el nombre de la variable para no tocar cada
  selector que ya la usaba.
- `#ticket-lineas` pasó de `<ul>`/`<li>` a `<table>` (`.tabla-ticket`) con
  encabezado Nombre/Cantidad/Precio/Total y un mensaje de estado vacío
  ("No hay artículos..."), en `pos_retail.html` y `pos_hospitalidad.html`
  (comparten la misma estructura y la misma función `actualizarTicket()`
  en `app.js`, así que se actualizaron los dos).
- Efecto secundario esperado: el reskin es global (aplica también a
  Hospitalidad y a las pantallas de administración), ya que es un cambio
  de variables de tema, no de una vista puntual.

### 2026-09-07 — Reconciliación del layout de Retail estilo Aronium
- El desarrollador intentó adaptar a mano `pos_retail.html`/`style.css`
  siguiendo la captura de Aronium (buscador arriba, ticket amplio, panel
  de acciones a la derecha con atajos F2-F12), pero reportó que "no quedó
  armónica" y que las funcionalidades existentes (grilla de productos con
  buscador/categorías) dejaron de servir. Causas encontradas:
  1. El nuevo CSS usaba colores fijos (`#2c2c2c`, `#333`, etc.) en vez de
     las variables de `:root`, por lo que no coincidía con la paleta del
     resto de la app (Productos/Inventario/Alertas) al navegar entre
     secciones.
  2. El HTML nuevo eliminó `#productos-grid` y `#categorias-tabs` por
     completo: el buscador seguía en el DOM pero ya no tenía nada que
     filtrar.
  3. El mensaje de vacío se renombró a `#ticket-vacio-msg`, pero
     `app.js` seguía buscando `#ticket-vacio` — nunca se ocultaba.
- Se confirmó con el desarrollador que la grilla de productos clicables
  se debía **conservar** (a diferencia de la Aronium real, que no la
  tiene) por ser mejor para un mostrador táctil. Se reconstruyó
  `pos_retail.html` con: buscador arriba, ticket + totales (Subtotal/
  Impuestos aún estáticos, no calculados) + la grilla con categorías
  debajo, y el panel de acciones a la derecha.
- Se reescribió el bloque CSS del panel de acciones para usar las
  variables de tema existentes (integración visual con el resto de la
  app) y se quitó el logo/marca de "aronium" que había quedado en el
  diseño de referencia (no corresponde dejar la marca de un producto de
  otra empresa en este proyecto).
- **Solo están conectados de verdad**: el buscador+categorías (ya
  existían), la grilla de productos, y el botón "F10 Pago" (=
  `#btn-cobrar`, cobra la orden). El resto de botones del panel
  (Eliminar, F3 Buscar, F4 Cantidad, F8 Nueva venta, Cash/Card/Check,
  Descuento, Price, Customer, Guardar venta, Reembolso, Bloquear,
  Transferir, Anular orden) son decorativos por ahora — matriz de
  próximos pasos de esta adaptación, no de este arreglo puntual.
- Verificado con navegador headless en Retail (vacío, con items, filtro
  de categoría) y en Hospitalidad (crear mesa, vender), sin errores de
  consola.

### 2026-09-07 — Formato numérico: punto de miles, coma decimal
- A pedido del desarrollador, todos los valores numéricos que se
  **muestran** (precios, cantidades, costos) usan la convención
  latinoamericana: punto para miles, coma para decimales (ej.
  `$1.234,50`, cantidad `2.994`), en vez del `1234.50` que traía por
  defecto `Number.prototype.toFixed()`.
- Se centralizó en `frontend/js/app.js`: `formatearMoneda(valor)` (2
  decimales fijos, con `$`) y `formatearCantidad(valor)` (hasta 3
  decimales, sin ceros de relleno — así "1" sigue viéndose como "1" y no
  como "1,000"). Reemplazó a todos los `` `$${Number(x).toFixed(2)}` ``
  dispersos por Retail, Hospitalidad, Productos, Inventario y Alertas.
- **Los `<input type="number">` de los formularios NO se tocaron**: ese
  tipo de input siempre usa punto decimal internamente (`.value` en el
  DOM), sin importar el idioma — es una limitación del propio tipo de
  campo HTML, no algo que esta app controle. Solo cambió lo que se
  **muestra** (grillas, tickets, tablas); lo que se **tipea** sigue el
  estándar del navegador. (Nota: en esta sesión, Chromium visualmente
  mostraba el input ya con coma decimal por la configuración regional del
  navegador — es un detalle del navegador del desarrollador, no algo que
  el código fuerce.)

### 2026-09-07 — Panel de Administración (submenú) + sección Configuración
- El desarrollador pidió agrupar Productos/Inventario/Alertas bajo un
  "panel de administración" propio, separado de Venta, ya que su
  siguiente foco es mejorar la creación de productos. Se implementó como
  un solo ítem de nivel superior "Administración" en la barra lateral que
  despliega un submenú (Productos, Inventario, Alertas, Configuración) —
  la alternativa de dejarlas sueltas y solo agregar Configuración se
  descartó a favor de esta.
- Nueva sección **Configuración** con dos partes, ambas con tablas nuevas
  (`backend/models/config.py`, endpoints en `config_router.py`):
  - `configuracion_negocio`: fila única (singleton, id=1) con nombre,
    NIT, dirección y teléfono del negocio — pensada para cuando el
    Módulo Contable necesite facturar (fase posterior).
  - `impresoras`: catálogo de nombres de impresora, para que el campo
    "Impresora destino" del formulario de Productos pase de texto libre
    a un `<select>` poblado desde aquí (evita typos como "Barra" vs
    "barra" que romperían el ruteo de comandas en Hospitalidad).
- Gotcha de CSS que ya había aparecido antes con `[hidden]` (ver sección
  6-E): el submenú (`#admin-submenu`) necesitó `:not([hidden])` en su
  regla de `display: flex` por la misma razón — se aplicó desde el
  principio esta vez, sin tener que redescubrir el bug.
- Verificado con navegador headless: expandir/colapsar el submenú,
  guardar datos del negocio y confirmar que persisten tras recargar la
  página, agregar impresoras y verificar que el `<select>` de Productos
  las lista correctamente.

### 2026-09-07 — Formulario completo de registro de productos
- A pedido del desarrollador (su prioridad declarada desde el principio),
  se amplió el formulario de Productos con: código (SKU manual), botón
  para generar un código de barras EAN-13 válido (con dígito verificador
  calculado), unidad de medida (lista fija: Unidad/Kg/Gramo/Litro/
  Mililitro/Libra, sin mostrarse junto a las cantidades ya construidas —
  decisión explícita para no reabrir varias pantallas ya verificadas),
  costo + margen de ganancia autocalculado (de solo lectura, nunca se
  guarda en la base de datos), interruptor de impuesto incluido,
  proveedor (catálogo nuevo, gestionado en Configuración igual que
  Impresoras), interruptores de activo/es servicio/stock bajo (este
  último con un campo de umbral que solo aparece si el interruptor está
  encendido), descripción, notas eliminables, e imagen con recorte
  automático a un cuadrado fijo sin importar el tamaño/proporción
  original.
- **`categoria` se renombró a `grupo`** en todo el stack (era el mismo
  concepto, solo el nombre cambió, a pedido explícito del desarrollador).
- **Nueva regla de negocio real, no solo de UI**: un producto marcado
  "es servicio" no descuenta inventario al venderse
  (`services/ventas.py`) — antes de este cambio, vender cualquier
  producto sin lotes fallaba con 409 "stock insuficiente"; ahora eso
  solo aplica a productos físicos.
- **Imágenes**: se agregó Pillow (`ImageOps.fit`) y se montó `/media`
  como archivos estáticos (`backend/data/imagenes_productos/`, ignorado
  por git). Es la primera vez que el backend maneja `multipart/form-data`
  (antes todo era JSON) y sirve archivos estáticos.
- **Tercera vez en la sesión que aparece el mismo bug de CSS** (`[hidden]`
  vencido por una regla de autor con `display`, ver 6-E): esta vez en
  `.imagen-preview` y en `.form-inline .campo` (el campo de umbral de
  stock bajo se veía siempre, sin importar el interruptor). Se corrigió
  con `:not([hidden])` como las veces anteriores, y se hizo un barrido
  sistemático de **todos** los elementos que se ocultan con `.hidden` en
  `app.js` contra el CSS para no tener que descubrirlo una cuarta vez.
- Verificado con navegador headless: producto con todos los campos
  nuevos, margen recalculado en vivo (66,67% para costo 15.000 / precio
  25.000), imagen 1200x300 subida y recortada a 400x400, dos notas
  agregadas, y un producto "Domicilio" marcado como servicio vendido
  desde Retail sin ningún lote creado (sin el 409 que sí ocurre con
  productos físicos sin stock).

### 2026-09-07 — Fix: `barcode.js` bloqueaba escribir en cualquier campo de texto
- El desarrollador reportó que no podía escribir en las casillas del
  formulario de Productos: el texto tecleado terminaba apareciendo en la
  barra inferior (el campo oculto `#barcode-input`). Esto **no se
  detectó en las pruebas anteriores de esta sesión** porque los scripts
  usaban `page.fill()` (que asigna el valor directo vía CDP), mientras
  que un click + tecleo real dispara una condición de carrera que
  `page.fill()` no reproduce.
- Causa raíz: `barcode.js` fue diseñado cuando la única pantalla era la
  caja (sin campos de texto reales, solo tarjetas/botones), y reenfoca
  `#barcode-input` ante cualquier clic fuera de él y cada 1.5s por
  temporizador, sin excepción. Al agregar formularios de administración
  reales, este comportamiento le quitaba el foco a cualquier input en
  cuanto el usuario hacía clic para empezar a escribir.
- Arreglo: `enfocar()` ahora respeta cualquier campo editable real
  (`input`/`textarea`/`select`/`contenteditable`) que ya tenga el foco,
  y solo reclama el foco cuando el elemento activo es algo no-editable
  (una tarjeta, un botón, el body). Esto no requirió tocar `app.js`: es
  un fix general en `barcode.js` que también resuelve el mismo problema
  latente en el buscador de Retail (`#productos-buscador`), que tenía
  exactamente el mismo bug sin que nadie lo hubiera notado.
- Verificado con tecleo real simulado (click + `type()` letra por letra,
  no `fill()`), incluyendo una pausa de 1.8s a mitad de la escritura
  para confirmar que el temporizador tampoco interrumpe. Se confirmó
  además que el escaneo real en Retail sigue funcionando: al hacer clic
  en una tarjeta de producto (no editable), el foco vuelve correctamente
  a `#barcode-input` para que un lector físico siga funcionando sin
  tocar el mouse.

### 2026-09-07 — Revisión de los cambios del desarrollador en Inventario
- El desarrollador rediseñó `views/inventario.html` a un patrón
  resumen→detalle (tabla con stock total por producto y pestañas de
  grupo, que al hacer clic en una fila muestra los lotes de ese
  producto), agregando `Producto.stock_total` (property en el modelo,
  suma de `lote.cantidad_actual` de todos sus lotes) al esquema
  `ProductoOut`. Se le pidió a Claude revisar y mejorar el resultado.
- **Bug de rendimiento real encontrado**: `stock_total` se agregó al
  `ProductoOut` compartido por *toda* la app (Retail, Hospitalidad,
  Productos e Inventario cargan productos por el mismo
  `GET /inventario/productos`), y al no tener precargada la relación
  `lotes`, cada serialización disparaba una consulta SQL adicional
  *por producto* (N+1) en cada pantalla, no solo en Inventario. Se
  corrigió con `selectinload(Producto.lotes)` en
  `listar_productos` (`inv_router.py`): 2 consultas totales sin
  importar cuántos productos haya, en vez de N+1.
- **Mejoras agregadas** a la vista nueva:
  - Los productos marcados "es servicio" (ej. "Domicilio") ya no
    aparecen en el resumen: mostrar "0" ahí se leía como agotado,
    cuando en realidad el concepto de stock no les aplica.
  - Se conectó `stock_bajo_activo`/`stock_bajo_umbral` (campos que ya
    existían en el formulario de Productos pero no se usaban en
    ningún lado) para mostrar un badge rojo "Stock bajo" cuando el
    stock total cae al umbral definido — el propósito original de esos
    campos, que había quedado sin conectar.
  - Buscador por nombre/código/SKU, igual al patrón ya usado en Retail
    y Productos (antes solo había pestañas de grupo).
  - El encabezado de columna decía "Categoría" pero leía el campo
    `grupo` (inconsistencia arrastrada del renombre `categoria`→`grupo`
    de una sesión anterior); ahora dice "Grupo". La unidad de medida se
    muestra capitalizada ("Kg" en vez de "kg").
- Verificado con navegador headless: el resumen filtra por grupo y por
  texto (con tecleo real, no `fill()`), el badge de stock bajo aparece
  correctamente al fijarle un umbral a un producto en 0 stock, los
  servicios quedan fuera del listado, y Retail/Productos/Hospitalidad
  siguen funcionando igual tras el cambio de consulta compartido.

### 2026-09-07 — Toast de confirmación + cantidad inicial al crear un producto
- Se agregó un componente de notificación no bloqueante (`#toast` en
  `index.html`, `mostrarToast(mensaje, tipo)` en `app.js`) que reemplaza
  el silencio de antes al guardar un producto: aparece arriba a la
  derecha y se oculta solo a los 3 segundos. Reutilizable para otros
  formularios más adelante, aunque por ahora solo se conectó en
  Productos (lo pedido).
- **Cantidad inicial al crear**: se agregó un campo opcional "Cantidad
  inicial" (+ vencimiento opcional) que solo aparece mientras el
  producto NO tiene id todavía (crear, no editar). Si se llena, al
  guardar se registra automáticamente el primer lote en Inventario
  usando el `Costo` ya capturado en el formulario — sin tener que ir a
  Inventario aparte solo para el ingreso inicial de stock. No se
  agregó ningún endpoint nuevo: es el frontend encadenando
  `crearProducto()` + `crearLote()`, ambos ya existentes.
  - Si se indica cantidad pero no se llenó `Costo` (requerido por
    `LoteInventario.costo_adquisicion`), el producto se guarda igual
    pero se avisa con un toast de error que el lote no se pudo
    registrar, en vez de fallar la operación completa o guardar un
    costo incorrecto.
  - Al editar un producto ya existente, la sección queda oculta: los
    ingresos de mercadería posteriores siempre pasan por Inventario,
    para no crear un lote de más cada vez que se guarda un cambio
    menor (ej. corregir el nombre).
- Verificado con navegador: crear con cantidad+costo registra el lote
  (confirmado también contra `GET /inventario/lotes/producto/{id}`) y
  muestra "Producto y lote inicial guardados correctamente"; crear sin
  costo muestra el toast de error correspondiente; editar un producto
  ya existente no duplica lotes y muestra el toast simple.

### 2026-09-07 — Corregir un lote existente (no solo crear lotes nuevos)
- El desarrollador notó que no había forma de corregir el stock de un
  producto ya creado: solo se podían registrar lotes nuevos, nunca
  ajustar uno existente (ej. tras un conteo físico o un error de
  captura al ingresarlo).
- Se agregó `PUT /inventario/lotes/{id}` (`LoteInventarioUpdate` en
  `schemas.py`, todos los campos opcionales) y se conectó en
  Inventario con el mismo patrón que ya usa Productos: clic en una
  fila de la tabla de lotes carga su cantidad/costo/vencimiento en el
  formulario de arriba, el botón cambia a "Guardar cambios" y aparece
  "Cancelar edición"; al guardar, pisa ese lote en vez de crear uno
  nuevo (sin esto, cada corrección habría inflado el historial FIFO
  con lotes duplicados).
- Verificado con navegador: editar la cantidad de un lote existente
  (confirmado contra la API que sigue habiendo un solo lote, con el
  valor corregido, no uno nuevo) y editar su fecha de vencimiento,
  confirmando que se recarga correctamente en el campo `date` al
  volver a hacer clic en la fila.

## 9. Backlog / próximas fases

- [ ] Autenticación y roles de usuario (cajero, administrador).
- [ ] Migraciones versionadas (Alembic) para reemplazar el
      `create_all()` de desarrollo antes de ir a producción, tanto en LAN
      local como en nube.
- [ ] Automatizar el despliegue en la nube (Terraform/Bicep + CI/CD) en vez
      de los comandos manuales documentados en la sección 7.
- [ ] Gestión de secretos en la nube vía AWS Secrets Manager / Azure Key
      Vault, en vez de variables de entorno en texto plano.
- [ ] (Descartado por ahora, ver bitácora 2026-09-07) Sincronización
      automática entre una instancia local y una en la nube para el mismo
      negocio — quedaría como evolución futura si un cliente lo pide.
- [ ] Conexión real a impresoras térmicas por sitio (configuración de
      `ImpresoraConfig` vía variables de entorno o archivo de config).
- [ ] Empaquetado del frontend como aplicación de escritorio (Tauri o
      Electron).
- [ ] Módulo Contable: asientos de doble entrada, reportes de utilidad
      bruta, exportación contable.
- [ ] Primeros modelos predictivos en `services/ai/` (demanda, sugerencia
      de reorden) apoyados en el histórico de `orden_detalles` y
      `lotes_inventario`.
- [ ] Desactivar/eliminar mesas desde la UI (el campo `activo` ya existe
      en el modelo; el de productos ya se resolvió con el interruptor
      "Activo" del formulario — ver bitácora 2026-09-07).
- [ ] Un Dashboard/portada con métricas (ventas del día, etc.), separado
      de la sección Alertas que hoy solo muestra el semáforo.
- [ ] Otros pendientes de pulir en Retail (discutidos con el desarrollador
      2026-09-07, no priorizados aún): captura de cantidad/peso exacto al
      hacer clic en un producto tipo "peso" (hoy suma "1" ambiguo),
      edición del ticket en curso (quitar/ajustar una línea, cancelar la
      venta sin cobrar), y cobro con efectivo + cálculo de cambio.
- [ ] Panel de acciones de Retail (Eliminar, F3 Buscar, F4 Cantidad, F8
      Nueva venta, Cash/Card/Check, Descuento, Price, Customer, Guardar
      venta, Reembolso, Bloquear, Transferir, Anular orden): hoy son
      botones decorativos sin lógica real, salvo el buscador y "F10 Pago".
- [ ] Editar/eliminar proveedores e impresoras desde la UI (hoy Proveedores
      solo permite listar/crear; Impresoras sí permite eliminar).
- [ ] Eliminar la imagen de un producto desde la UI (hoy solo se puede
      reemplazar subiendo una nueva).
- [ ] Subtotal/Impuestos reales en el ticket de Retail (hoy son "$0,00"
      estáticos): requiere definir de dónde sale la tasa de impuesto,
      aprovechando el nuevo interruptor `incluye_impuesto` del producto.
