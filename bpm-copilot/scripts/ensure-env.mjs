// Crea .env a partir de .env.example si aún no existe (evita un paso manual).
import { existsSync, copyFileSync } from "node:fs";

if (!existsSync(".env")) {
  if (existsSync(".env.example")) {
    copyFileSync(".env.example", ".env");
    console.log("→ Creado .env a partir de .env.example");
  } else {
    console.warn("⚠ No se encontró .env.example; crea un .env manualmente.");
  }
}
