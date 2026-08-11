# Imagen para publicar la herramienta con contraseña.
#
# Construye la interfaz y la sirve desde el mismo proceso que la API: asi la
# cookie de sesion no cruza dominios y SameSite=Strict la protege de verdad.
#
# La herramienta sigue siendo de SOLO LECTURA: no envia ordenes a ningun broker.

# --- 1. Compilar la interfaz ------------------------------------------------
FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- 2. Imagen final --------------------------------------------------------
FROM python:3.12-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY connectors/ connectors/
COPY models.py sectors.py consolidation.py storage.py report.py httpclient.py main.py ./
COPY --from=frontend /build/dist frontend/dist

# La base de datos vive en un volumen. Sin esto, cada despliegue borraria tus
# datos: el disco del contenedor es efimero.
ENV INVEST_DB=/data/personal_invest.db \
    INVEST_CACHE=/data/.cache
VOLUME ["/data"]

# No ejecutar como root: si algo se cuela, que tenga los menos permisos posibles.
RUN useradd --create-home --uid 10001 app \
 && mkdir -p /data && chown -R app:app /data /app
USER app

EXPOSE 8000

# Sin APP_PASSWORD_HASH la aplicacion arranca ABIERTA. Configura esa variable en
# tu plataforma antes de exponerla a internet.
CMD ["python", "-m", "uvicorn", "app.main:app", "--app-dir", "backend", \
     "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
