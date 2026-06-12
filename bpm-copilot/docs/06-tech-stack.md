# 6 · Stack tecnológico

Criterio: **gratis o incluido en tu suscripción**, sin dependencia obligatoria
de APIs pagadas, compatible con Claude Code.

| Capa | Tecnología | Por qué |
|---|---|---|
| **Framework** | Next.js 15 (App Router) | Full-stack en un proyecto, Server Actions, ruta directa a SaaS. Gratis (MIT). |
| **Lenguaje** | TypeScript | Type-safety extremo a extremo; un solo lenguaje front+back. |
| **ORM** | Prisma 6 | Esquema declarativo, migraciones, type-safe. SQLite→Postgres sin cambiar código. |
| **Base de datos** | SQLite (dev) → Postgres (SaaS) | Local-first, cero infra. Neon/Supabase tienen tier gratis para SaaS. |
| **UI** | Tailwind CSS 3 | Estilos rápidos sin librería pesada de componentes. |
| **Validación** | Zod | Valida la salida del LLM y los modelos de dominio. |
| **IA** | Claude / Ollama / Mock (agnóstico) | Default Claude (tu suscripción); Ollama gratis local; Mock cero coste. |
| **Runtime scripts** | tsx | Ejecuta seed y verificación sin build. |

## Por qué este stack y no otros

- **vs. Python (FastAPI) + React separados**: dos lenguajes, dos despliegues,
  contratos duplicados. Next.js unifica y reduce fricción para un MVP de una
  persona con visión de equipo.
- **vs. Supabase/Firebase de inicio**: añaden dependencia de servicio y coste
  potencial. Local-first con SQLite es gratis y privado; la migración a Postgres
  gestionado es un cambio de `DATASOURCE`, no de código.
- **vs. LLM acoplado (SDK directo en el dominio)**: rompería el requisito de
  "evitar APIs pagadas". El puerto/adaptador mantiene la opción abierta.

## Compatibilidad con Claude Code
- Proyecto estándar Node/TypeScript: Claude Code navega, edita y ejecuta sin
  configuración especial.
- Scripts npm claros (`dev`, `build`, `db:*`, `typecheck`) para automatizar.
- Sin binarios propietarios ni pasos manuales ocultos.

## Costes
- **Desarrollo y uso personal**: $0 (SQLite + adaptador mock/ollama).
- **Con Claude**: solo el coste por transcripción procesada (puntual, no continuo).
- **SaaS**: Vercel Hobby + Neon free tier permiten empezar sin coste fijo.
