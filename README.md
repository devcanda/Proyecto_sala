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

### 2026-09-08 — Marco visual estilo Aronium (paso 1: el armazón)

- El desarrollador planteó que el programa "aún dista mucho de parecerse a
  Aronium" y preguntó si era viable calcar primero la parte visual y
  trabajar la lógica de cada apartado después. Se acordó: **marco ahora,
  detalle después**, y solo sobre las 6 pantallas que ya existen (Retail,
  Hospitalidad, Productos, Inventario, Alertas, Configuración), sin
  maquetar secciones que Aronium tiene y este proyecto todavía no
  (Clientes, histórico de documentos, reportes).
- **Riesgo identificado antes de tocar nada.** El intento anterior de
  adaptar el layout a mano (ver bitácora del 2026-09-07) rompió
  funcionalidad porque el HTML nuevo eliminó `#productos-grid` y
  `#categorias-tabs` y renombró `#ticket-vacio`, sin que apareciera ningún
  error en consola. La causa de fondo es que `app.js` está acoplado al
  HTML por identificadores de elemento: hoy busca 94 ids que las vistas
  deben seguir proveyendo.
- **Mitigación: `scripts/verificar_contrato_dom.py`** (nuevo). Compara los
  ids que busca el JS contra los que define el HTML, comprueba los
  enganches por clase (`.seccion-btn[data-seccion]`, `.modo-btn[data-modo]`)
  y la presencia de `#barcode-input`. Devuelve código 1 si algo se rompe,
  así que sirve para un hook de pre-commit. La regla de trabajo para esta
  fase visual es: el CSS y el marcado envolvente son libres, pero todo
  elemento que cargue uno de esos ids debe sobrevivir con el mismo id.
- **Qué cambió en el tema (`frontend/css/style.css`):**
  1. `--radius` pasó de `10px` a `2px`. Era el detalle que más delataba un
     POS "hecho en web": Aronium es una app WinForms y casi no redondea.
  2. Paleta de grises neutros de escritorio (`#1e1e1e` / `#252526` /
     `#2d2d30`) en vez del casi-negro azulado anterior (`#101317`), más
     `--color-seleccion` (azul tipo Explorador) para lo seleccionado.
     `--color-primary-dark` conserva su rol invertido y su nota.
  3. Densidad global vía `html { font-size: 14px }`. Como toda la hoja
     está en `rem`, comprime la interfaz de forma proporcional sin
     reescribir cada `padding`. Se agregaron variables de alto fijo
     (`--alto-barra`, `--alto-control`, `--alto-statusbar`) para que las
     barras y los controles se alineen entre pantallas.
  4. `button, input, select, textarea { font-family: inherit }`: sin esto
     **ningún** botón del proyecto usaba Segoe UI, sino la fuente por
     defecto del navegador.
- **Qué cambió en el armazón (`frontend/index.html`):**
  1. El `body` es una columna flex de alto fijo y el scroll pasó a ser
     interno de `.app-view`. Una app de escritorio no hace scroll de
     página.
  2. Barra lateral densa: filas de alto fijo, sin pastillas, con barra de
     acento a la izquierda en el item activo, e **iconos SVG en línea**.
     Van en línea y no como fuente de iconos ni CDN a propósito: el modo
     Standalone tiene que funcionar sin internet.
  3. **Barra de estado inferior nueva.** Recoge dos elementos que andaban
     sueltos: `#barcode-input`, que flotaba con `position: fixed` contra
     el borde y tapaba el final del contenido, y `#connection-status`, que
     estaba al pie de la barra lateral donde nadie lo mira.
- **Primitivas compartidas** (afectan a las 6 pantallas de una vez):
  pestañas de categoría rectas en vez de pastillas, catálogo de productos
  como retícula compacta, `.tabla-admin` convertida en rejilla de datos
  (filas bajas, cabecera fija en mayúsculas, resaltado de fila completa),
  `.panel-admin` con barra de título propia, y botones, campos, etiquetas
  de estado y selector de archivo compactos y rectos.
- **Verificación.** Contrato del DOM en verde (94 ids buscados, 0
  huérfanos). Prueba funcional con navegador headless: el foco arranca en
  el lector, escanear un código real agrega la línea al ticket, el
  multiplicador `3*código` da el total esperado, escribir en un campo de
  formulario ya no se lo roba el lector, y las 6 pantallas navegan sin
  errores de consola.
- **Deliberadamente NO se tocó**, porque corresponde a la fase de detalle
  contra capturas reales: los iconos emoji del panel de acciones de Retail
  (se ven a color y desentonan con los iconos monocromos del marco), los
  interruptores deslizantes de Productos (en Aronium serían casillas de
  verificación), y la barra de comandos que Aronium pone encima de cada
  rejilla (Nuevo / Editar / Eliminar / Actualizar) — no se agregó para no
  sumar más botones decorativos sin lógica.

### 2026-09-08 — Calco de la pantalla de venta (paso 2: Retail contra la captura real)

- El desarrollador aportó la captura real de la pantalla de venta de
  Aronium y pidió, además, que **las opciones de administración quedaran
  alojadas en los tres puntos rojos de la esquina inferior derecha**.
- **Qué se calcó** (`frontend/views/pos_retail.html` + bloque nuevo en
  `style.css`): barra superior con los cuatro modos de búsqueda y el
  buscador sin recuadro; cabecera del ticket con el subrayado azul;
  mensaje de vacío centrado en el hueco del ticket; totales anclados abajo
  a la derecha con separador punteado y TOTAL en grande; y el panel de
  acciones de 4 columnas con el atajo de teclado en la esquina superior
  izquierda de cada botón, Cash/Card/Check distinguidos por una línea de
  color en el borde inferior (no por relleno), F10 Pago en verde ocupando
  dos columnas, y Anular orden en rojo.
- **Iconos.** Se reemplazaron los emoji del panel (🔍 💰 🏷 👤 💾 🗑) por un
  sprite SVG monocromo (`<symbol>` + `<use>`) en la propia vista. Iban a
  color y desentonaban con el resto del marco. Va en línea, no como fuente
  de iconos ni CDN, porque el modo Standalone debe funcionar sin internet.
- **Navegación: la barra lateral desaparece en Venta.** La pantalla de caja
  de Aronium es a sangre, sin barra lateral, y el pedido de alojar
  Administración en los tres puntos solo tiene sentido si la barra deja de
  cargarla. Se resolvió así:
  1. `#btn-admin-toggle` pasó a ser el botón de los tres puntos, fijo en la
     esquina inferior derecha, y `#admin-submenu` su menú desplegable.
  2. **Ambos siguen viviendo en `index.html`, no en la vista.** Es una
     restricción real, no una preferencia: `init()` los enlaza por id una
     sola vez al arrancar, *antes* de inyectar ninguna vista, y
     `marcarSeccionActiva()` los consulta en cada cambio de sección. Si se
     mudaran a `pos_retail.html`, `init()` reventaría al arrancar y también
     al entrar a cualquier sección de administración. El botón toma sus
     medidas de las mismas variables CSS que la retícula del panel
     (`--ancho-acciones`, `--alto-celda-accion`) para encajar en su última
     celda sin desalinearse.
  3. La barra lateral **sí** aparece en las secciones de administración,
     para saber dónde se está y poder volver. Lo decide el CSS mediante
     `body[data-seccion]`, que `marcarSeccionActiva()` ahora mantiene.
  4. Los botones de navegación están duplicados a propósito (barra lateral
     y menú). No es un problema porque `app.js` los enlaza por clase y
     atributo de datos, no por id.
- **Comportamiento del menú** (`app.js`): antes el submenú se forzaba
  abierto mientras se estuviera en una sección de administración, que era
  correcto para un submenú fijo dentro de la barra lateral pero dejaba un
  menú flotante pegado en pantalla. Ahora se abre y se cierra con el botón,
  y se cierra al elegir una opción, al pulsar fuera y con Escape.
- **Desviaciones deliberadas respecto al original**, todas documentadas en
  la cabecera de `pos_retail.html`:
  1. Se conserva la grilla de productos táctil, que la Aronium real no
     tiene (decisión del 2026-09-07). Se colocó en la banda central del
     panel de acciones, que en el original está vacía con la marca de agua
     del logo, así el ticket queda tan amplio como en la captura.
  2. No se reproduce el logo de Aronium: es marca de otra empresa.
  3. Los importes mantienen el formato del proyecto (`$25.000,00`) en vez
     del `0.00` del original.
  4. Se mantiene la barra de estado inferior, que el original no tiene,
     porque `#barcode-input` debe seguir visible y enfocable en todas las
     pantallas (regla 5-B). Se dejó lo más discreta posible.
- **Dos correcciones que salieron del calco**: el `<br/>` que
  `renderProductosGrid()` mete en cada ficha contaba como un elemento más
  dentro del contenedor flex y abría un hueco entre el nombre y el precio;
  y el `display: block` del `<strong>` del mensaje de ticket vacío se había
  perdido, dejando el titular y la explicación en la misma línea (afectaba
  también a Hospitalidad, que comparte ese mensaje).
- **Verificación.** Contrato del DOM en verde. Prueba funcional con
  navegador headless, 8 comprobaciones: el foco arranca en el lector, la
  barra lateral está oculta en Venta y visible en Productos, escanear
  agrega la línea, el multiplicador `3*código` da `$100.000,00`, el menú
  abre y se cierra al elegir y con Escape, escribir en un formulario no se
  lo roba el lector, y las 6 pantallas navegan sin errores de consola.
- **Sigue pendiente**: los botones del panel siguen siendo decorativos
  salvo el buscador, las fichas y F10 Pago; los cuatro modos de búsqueda de
  la barra superior son decorativos (hoy el buscador ya filtra por nombre y
  código a la vez); y Hospitalidad y las pantallas de administración
  esperan sus propias capturas de referencia.

### 2026-09-08 — El lector de código de barras pasa al buscador de la pantalla

- El desarrollador pidió quitar la barra de captura del lector de la
  esquina inferior izquierda, porque el código debe entrar por el mismo
  buscador de arriba. Era redundante tener dos campos para lo mismo.
- **Qué se quitó.** `#barcode-input`, el campo dedicado que vivía fijo en
  la barra de estado. La barra de estado se queda solo con el indicador de
  conexión.
- **Cómo funciona ahora.** El campo de captura del lector se declara en el
  HTML con el atributo `[data-captura-barras]`, y es el propio buscador de
  cada pantalla de venta. `barcode.js` dejó de ser dueño de un campo fijo:
  1. Busca el campo de captura de la vista actual cada vez que lo necesita,
     porque las vistas se inyectan y se destruyen en cada cambio de
     pantalla.
  2. Solo lo considera si está **visible** (`offsetParent`). Sin esa
     guarda, en Hospitalidad pelearía por el foco del buscador de la
     cuenta mientras todavía se está eligiendo mesa.
  3. Escucha el Enter **delegado en `document`**, no enlazado al campo, por
     la misma razón: el campo nace y muere con cada vista, así que no se le
     puede enlazar un listener una sola vez al arrancar.
  4. Ya no limpia el campo al pulsar Enter. Lo limpia `app.js` sólo cuando
     el escaneo prosperó, para que un código no reconocido quede a la vista
     y se pueda corregir.
- **Hospitalidad también necesitaba uno.** No tenía buscador, y su panel de
  cuenta documenta explícitamente el escaneo ("Escanea un código de barras,
  o escribe `5*codigo`..."). Sin un campo propio, quitar el global habría
  roto ese flujo en silencio. Se le añadió el mismo buscador, que de paso
  le da el filtrado de productos que le faltaba.
- **Consecuencia de compartir campo: el Enter ahora es ambiguo.** Puede
  venir del lector, que teclea un código exacto, o de una persona buscando
  por nombre. `onBarcodeScan()` se reescribió para resolverlo por orden de
  certeza:
  1. Coincidencia exacta de código contra el catálogo ya cargado. Es el
     caso del lector y se resuelve sin salir a la red.
  2. Si el filtro dejó **un único** producto a la vista, se agrega ese. Va
     antes de consultar al backend para que teclear un nombre no dispare
     una petición condenada al 404. No puede confundirse con un escaneo:
     si el código leído no está en el catálogo, el filtro no deja ningún
     producto visible y este caso no se cumple.
  3. Consulta al backend, que cubre un código existente en la base pero no
     en el catálogo en memoria (por ejemplo, un producto dado de alta desde
     otra caja en modo Red LAN).
  4. Si no queda ningún candidato, se avisa. **El aviso pasó de `alert()` a
     un toast**: un diálogo bloqueante saltaría ahora ante cualquier
     búsqueda sin resultados y habría que descartarlo a mano.
- **Dos arreglos que exigía el cambio:**
  1. `productosFiltrados()` sólo aplica el filtro por categoría donde hay
     pestañas para cambiarlo. En la cuenta de Hospitalidad no las hay, y
     sin esa guarda arrastraría la categoría elegida en Retail, escondiendo
     productos sin forma de deshacerlo desde esa pantalla.
  2. El listener del buscador salió de la rama exclusiva de Retail, porque
     ahora los dos modos traen ese campo.
- **`scripts/verificar_contrato_dom.py` actualizado**: donde antes exigía
  `#barcode-input`, ahora comprueba que cada pantalla de venta declare su
  `[data-captura-barras]`. Es la misma regla de UX, sobre otro campo.
- **Verificación.** Contrato en verde. Prueba funcional con navegador
  headless, 9 comprobaciones: `#barcode-input` ya no existe, el foco
  arranca en el buscador, escanear agrega la línea y limpia el campo, el
  multiplicador da el total esperado, buscar por nombre y pulsar Enter
  agrega el único producto visible, un texto sin resultados avisa por toast
  y no por diálogo bloqueante, Hospitalidad conserva su campo de captura
  sin robar el foco mientras la cuenta está oculta, escribir en un
  formulario de administración sigue sin verse interrumpido, y las 6
  pantallas navegan sin excepciones de JavaScript.

### 2026-09-08 — Motor de búsqueda de la venta (modos + desplegable de resultados)

- Segundo juego de capturas del desarrollador, esta vez sobre el buscador:
  qué pasa al pulsar cada tipo de búsqueda y cómo se ve un producto
  encontrado. Los cuatro botones de la barra superior, que hasta ahora eran
  decorativos, quedaron funcionando.
- **Los cuatro modos** (`MODOS_BUSQUEDA` en `app.js`, claves espejadas en
  los `data-modo-busqueda` de `pos_retail.html`). Cada uno cambia tres
  cosas a la vez:

  | Modo | Busca en | Texto de ayuda |
  |---|---|---|
  | Todos (asterisco) | nombre, código y código de barras | Buscar producto por nombre, código o código de barras |
  | Código de barras | `codigo_barras` | Buscar producto por código de barras |
  | Código (almohadilla) | `codigo` | Buscar producto por código |
  | Nombre (etiqueta) | `nombre` | Buscar producto por nombre |

  Además del texto de ayuda, el modo cambia el icono que lleva el campo a
  la izquierda: código de barras en ese modo, lupa en el resto. El modo
  elegido se recuerda en `localStorage`, igual que el modo de venta.
- **Ayudas emergentes** dibujadas con CSS y no con el atributo `title` del
  navegador, que tarda casi un segundo en aparecer y se pinta con el estilo
  del sistema, fuera del tema oscuro.
- **Desplegable de resultados** (`#resultados-busqueda`): cae bajo el campo
  y por encima del ticket, con el nombre a la izquierda y el precio
  alineado a la derecha en cifras de ancho fijo. La primera fila viene
  resaltada. Las flechas mueven la selección, Enter agrega la resaltada,
  el clic agrega la fila pulsada y Escape lo cierra. Está topado a 40
  filas: con un catálogo grande, repintar cientos de filas en cada tecleo
  se nota y nadie recorre una lista así.
- **El Enter pasa a resolverse por el desplegable.** `onBarcodeScan()`
  gana un paso previo: si el desplegable está abierto, manda la fila
  resaltada. Cubre los dos caminos con el mismo código, porque el lector
  deja una única coincidencia ya resaltada y el teclado deja la que el
  operario eligió con las flechas. Debajo siguen intactos los pasos
  anteriores (código exacto en memoria, coincidencia única visible,
  consulta al backend, aviso por toast), que son los que atienden a
  Hospitalidad, que todavía no tiene desplegable.
- **El multiplicador sigue valiendo con nombres.** Escribir `3*aceite`
  busca "aceite" y agrega 3. Para lograrlo, `barcode.js` expone su parser
  (`window.barcodeFocus.parsear`) y el buscador lo reutiliza, en vez de
  duplicar la regla del `N*`.
- **Guarda para Hospitalidad**: donde no hay selector de modo se busca
  siempre por todos los campos. Sin eso, un modo restringido elegido en
  Retail viajaría a la cuenta de una mesa y allí sería imposible cambiarlo.
  Es la misma clase de guarda que ya se puso para el filtro por categoría.
- La grilla táctil de productos filtra con el mismo criterio que el
  desplegable, así que las dos superficies siempre coinciden. Se mantiene
  aunque Aronium no la tenga, por la decisión del 2026-09-07.
- **Verificación.** Contrato del DOM en verde. Prueba nueva del buscador,
  10 comprobaciones: existen los cuatro modos con uno solo activo, cada uno
  pone su texto de ayuda, el icono del campo cambia en modo código de
  barras, buscar un nombre en modo código de barras no devuelve nada, el
  mismo nombre en modo nombre sí y con la primera fila resaltada, las
  flechas mueven la selección, Enter agrega y limpia y cierra, el clic
  agrega, el escaneo por código sigue funcionando, y el modo sobrevive a
  recargar. Se volvió a pasar la prueba de regresión anterior, con sus 9
  comprobaciones en verde.

### 2026-09-08 — Tirador para ajustar el ancho del panel de acciones

- Tercera captura del desarrollador, señalando en rojo el agarre vertical
  del borde entre el ticket y el panel de acciones: sirve para arrastrar
  ese borde y dar más o menos ancho al panel.
- **Cómo se implementó.** Una franja estrecha (`#separador-acciones`) entre
  las dos zonas, con cursor de ajuste. Se arrastra con el puntero y el
  doble clic devuelve el panel a su ancho de fábrica.
- **El detalle que gobierna todo lo demás:** el ancho se escribe en la
  variable CSS `--ancho-acciones` **de la raíz del documento**, no del
  elemento de la vista. El botón de los tres puntos vive en `index.html`,
  fuera de la vista, y calcula su tamaño con esa misma variable para
  encajar en la última celda de la retícula. Si el ancho se guardara en la
  vista, el botón no se enteraría y los dos se desalinearían en cuanto se
  arrastrara el tirador. La prueba mide ese desajuste y lo exige por debajo
  de 3px.
- **Captura del puntero** (`setPointerCapture`) durante el arrastre: la
  franja mide unos pocos píxeles y sin eso el gesto se pierde en cuanto el
  cursor se sale de ella. La clase `redimensionando` en el `<body>` fija
  además el cursor de ajuste en toda la ventana mientras dura el gesto.
- **Topes**: mínimo 240px, y máximo el menor entre 640px y el 60% de la
  ventana, para que ninguna de las dos zonas se coma a la otra. Al cambiar
  el tamaño de la ventana se vuelve a aplicar el tope, pero sin regrabar el
  valor: un recorte por ventana angosta no debe pisar la preferencia del
  usuario, que vuelve al ensanchar.
- El ancho se recuerda en `localStorage`. El doble clic **borra** la
  propiedad en línea en vez de escribir un número, para que el valor por
  defecto siga viviendo solo en la hoja de estilos y no haya que repetirlo
  en el JavaScript.
- Tras soltar el tirador el foco vuelve al buscador, para que el lector de
  código de barras pueda disparar inmediatamente después.
- Los puntos del agarre se dibujan con un degradado radial repetido y no
  con el carácter `⋮`, para que salgan idénticos en cualquier equipo sin
  depender de qué fuente resuelva ese glifo.
- **Corrección el mismo día: el tirador no se veía.** La primera versión
  usaba puntos de 1,2px en una franja de 3x22px y en gris apagado
  (`--color-text-muted`). Estaba en su sitio y arrastraba bien, y las
  pruebas automáticas pasaban, porque comprueban el comportamiento y no si
  algo se distingue a simple vista. El desarrollador lo reportó como que el
  botón no se había agregado. Se pasó a puntos de 1,7px en 4x28px con
  `--color-text` al 70%, y la franja se ensanchó a 0,75rem con un fondo que
  se ilumina al acercar el puntero. La lección para el resto del calco: un
  control que se descubre mirando tiene que leerse sin buscarlo, y eso no
  lo cubre ninguna prueba funcional.
- **Sin teclado a propósito.** No se le puso `tabindex`: `barcode.js`
  devuelve el foco al buscador cada 1,5s salvo que se esté escribiendo en
  otro campo, así que un control enfocable que no es un campo de texto
  perdería el foco solo. Se ajusta con el puntero.
- **Verificación.** Contrato del DOM en verde. Prueba nueva del tirador, 8
  comprobaciones: existe con el cursor correcto, arrastrar a un lado
  ensancha y al otro estrecha, el botón de los tres puntos no se desalinea,
  los topes se respetan por ambos extremos, el ancho sobrevive a recargar,
  el doble clic restablece los 378px de fábrica, y el foco vuelve al
  buscador. Las dos baterías de regresión anteriores (buscador y
  lector/navegación) siguen en verde.
- **Visto en la misma captura, pendiente de pedir**: la línea del ticket
  trae un desplegable con una segunda línea de detalle (`#1 14:35 SKU:
  SKU-033`), los impuestos aparecen calculados de verdad, "Guardar venta"
  lleva un contador en rojo y el botón de cliente muestra un número. Nada
  de eso se tocó en este paso.

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
- [ ] Fase de detalle visual, pantalla por pantalla, contra capturas
      reales de Aronium. Retail ya está calcado (bitácora 2026-09-08);
      faltan Hospitalidad y las cuatro pantallas de administración, para
      las que todavía no hay captura de referencia. Pendientes conocidos:
      cambiar los interruptores deslizantes de Productos por casillas de
      verificación, y evaluar la barra de comandos por rejilla (Nuevo /
      Editar / Eliminar / Actualizar) una vez tengan lógica real.
- [ ] Llevar el desplegable de resultados a la cuenta de Hospitalidad, que
      hoy sólo tiene el campo de búsqueda (bitácora 2026-09-08).
- [ ] Correr `scripts/verificar_contrato_dom.py` como hook de pre-commit,
      en vez de a mano.
