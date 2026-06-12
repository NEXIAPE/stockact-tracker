# Copiloto BPM — imagen para ejecución local "casi un clic".
# Prioriza fiabilidad sobre tamaño (deja todas las dependencias).
FROM node:22-slim

# OpenSSL: requerido por Prisma.
RUN apt-get update && apt-get install -y openssl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instala dependencias (capa cacheable).
COPY package*.json ./
RUN npm install

# Copia el resto y construye.
COPY . .
# La base de datos vivirá en /app/data (volumen). DATABASE_URL se inyecta en runtime.
ENV DATABASE_URL="file:/app/data/dev.db"
ENV LLM_PROVIDER="mock"
ENV NODE_ENV="production"
RUN npx prisma generate && npm run build

EXPOSE 3000

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh
ENTRYPOINT ["/docker-entrypoint.sh"]
