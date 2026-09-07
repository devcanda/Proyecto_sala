# Dockerfile
# -----------
# Imagen del backend para el "Modo Red LAN" (ver docker-compose.yml).
# El modo Standalone (SQLite) no necesita esta imagen: corre directo con
# Python/uvicorn en la maquina de la caja registradora.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
