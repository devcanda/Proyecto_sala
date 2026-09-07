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
│   │   ├── inventory.py             # Producto, RecetaIngrediente, LoteInventario
│   │   └── pos.py                   # Mesa, Orden, OrdenDetalle
│   ├── routers/
│   │   ├── pos_router.py            # Ordenes, mesas, cobro
│   │   ├── inv_router.py            # Catálogo y lotes de inventario
│   │   └── alert_router.py          # Semaforización de vencimientos
│   ├── services/
│   │   ├── ventas.py                 # FIFO + expansión de escandallos
│   │   ├── hardware/printing.py      # Impresión térmica / cajón monedero
│   │   └── ai/                       # Reservado para modelos predictivos
│   └── data/                         # SQLite vive aquí (ignorado por git)
├── frontend/
│   ├── index.html                    # Shell: barra superior + input de barras
│   ├── views/
│   │   ├── pos_retail.html           # Fragmento: grilla de productos + ticket
│   │   └── pos_hospitalidad.html     # Fragmento: mapa de mesas + cuenta
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
| `productos` | `codigo_barras`, `tipo` (`unidad`/`peso`/`compuesto`), `precio_venta`, `impresora_destino` | Catálogo central; `impresora_destino` habilita el ruteo de comandas en Hospitalidad |
| `recetas_ingredientes` | `producto_compuesto_id`, `insumo_id`, `cantidad_requerida` | Tabla pivote de escandallos (ej. 1 Mojito = 50ml ron + azúcar + limón + 1 vaso) |
| `lotes_inventario` | `producto_id`, `cantidad_actual`, `costo_adquisicion`, `fecha_ingreso`, `fecha_vencimiento` | Existencias físicas por lote, base del FIFO y de la semaforización |
| `mesas` | `nombre`, `estado` (`libre`/`ocupada`/`reservada`) | Solo aplica en modo Hospitalidad |
| `ordenes` | `tipo_orden` (`directa`/`mesa`), `mesa_id`, `estado` (`abierta`/`pagada`/`cancelada`) | Cabecera del ticket o cuenta |
| `orden_detalles` | `cantidad` (decimal, admite gramos), `precio_unitario_historico` | Precio congelado al momento de la venta: base del futuro cálculo de utilidad bruta |

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
(`POST /pos/ordenes/{id}/pagar`) la mesa vuelve a estado `libre`.

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

## 9. Backlog / próximas fases

- [ ] Autenticación y roles de usuario (cajero, administrador).
- [ ] Endpoints CRUD completos para `recetas_ingredientes` (hoy solo se
      probó vía ORM directo; falta exponerlo en `inv_router.py`).
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
