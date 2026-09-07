"""
database.py
------------
Capa de conexion a base de datos via SQLAlchemy.

Soporta dos modos, seleccionados por la variable de entorno DB_MODE:

- "sqlite" (default): Modo Standalone, pensado para un negocio con conexion
  a internet intermitente o nula. Corre por completo en la maquina local,
  sin depender de ningun servidor externo. El archivo vive en backend/data/.

- "postgresql": Modo Servidor, para cualquier PostgreSQL alcanzable por red:
  desde un contenedor Docker en la LAN del negocio (orquestado via
  Portainer) hasta una base de datos administrada en la nube (AWS RDS,
  Azure Database for PostgreSQL). Es el mismo codigo en ambos casos; lo
  unico que cambia es a que host apunta POSTGRES_HOST y si se exige SSL
  (ver POSTGRES_SSLMODE), que los proveedores cloud suelen requerir.

Estos dos modos son despliegues INDEPENDIENTES: un negocio se instala en
uno u otro segun su conectividad, no se alterna automaticamente entre ellos
ni hay sincronizacion entre instancias.

El resto de la aplicacion (modelos, routers) nunca debe importar sqlite3 o
psycopg2 directamente: siempre debe pasar por `engine`, `SessionLocal` y
`get_db()` definidos aqui, de forma que cambiar de modo sea solo un cambio
de variable de entorno, no de codigo.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_MODE = os.getenv("DB_MODE", "sqlite").lower()

if DB_MODE == "postgresql":
    POSTGRES_USER = os.getenv("POSTGRES_USER", "salsa_pos")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB = os.getenv("POSTGRES_DB", "salsa_pos")
    # AWS RDS y Azure Database for PostgreSQL exigen (o recomiendan) SSL;
    # un Postgres local en Docker/Portainer normalmente no lo necesita.
    # Valores validos: disable, allow, prefer, require, verify-ca, verify-full.
    POSTGRES_SSLMODE = os.getenv("POSTGRES_SSLMODE", "prefer")

    SQLALCHEMY_DATABASE_URL = (
        f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
        f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_pre_ping=True,
        connect_args={"sslmode": POSTGRES_SSLMODE},
    )

else:
    # Modo Standalone: SQLite
    SQLITE_DB_NAME = os.getenv("SQLITE_DB_NAME", "salsa_pos.db")
    SQLITE_PATH = DATA_DIR / SQLITE_DB_NAME
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{SQLITE_PATH}"

    # check_same_thread=False es necesario porque FastAPI puede atender
    # una misma conexion desde distintos hilos (async workers).
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependencia de FastAPI: entrega una sesion por request y la cierra al final."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
