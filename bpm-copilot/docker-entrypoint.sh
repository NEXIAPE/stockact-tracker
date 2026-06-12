#!/bin/sh
# Arranque del contenedor: asegura la base de datos y siembra solo la primera vez.
set -e

mkdir -p /app/data

echo "→ Sincronizando esquema de base de datos…"
npx prisma db push --skip-generate

# Siembra datos de ejemplo solo si la base está vacía (primer arranque).
COUNT=$(node -e "const{PrismaClient}=require('@prisma/client');const p=new PrismaClient();p.project.count().then(c=>{console.log(c);process.exit(0)}).catch(()=>{console.log(0);process.exit(0)})")
if [ "$COUNT" = "0" ]; then
  echo "→ Base vacía: cargando datos de ejemplo…"
  npx tsx prisma/seed.ts || true
else
  echo "→ Base existente ($COUNT proyecto(s)). No se siembra."
fi

echo "→ Iniciando Copiloto BPM en http://localhost:3000"
exec npm run start
