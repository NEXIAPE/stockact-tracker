#!/usr/bin/env python3
"""
Ejecución diaria sin interfaz: refresca alertas y escribe el briefing en texto.

Pensado para cron, para que al abrir la herramienta por la mañana las alertas ya
estén calculadas en vez de tener que esperar a que se consulten las fuentes.

    .venv/bin/python backend/daily.py
    .venv/bin/python backend/daily.py --no-ideas --quiet

UNA VEZ AL DÍA ES SUFICIENTE. Las fuentes que usa esta herramienta son gratuitas
y sin garantía de servicio; consultarlas cada pocos minutos las castiga sin
darte nada a cambio, porque son cierres diarios. Y revisar la cartera a todas
horas es, además, una forma conocida de tomar peores decisiones.

Igual que el resto de la herramienta: SOLO LECTURA. No envía ninguna orden.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core import alerts as alerts_core  # noqa: E402
from app.core.briefing import build  # noqa: E402
from app.db import get_conn  # noqa: E402
from app.deps import load_profile  # noqa: E402
from app.core.portfolio import load_portfolio  # noqa: E402
from app.core.profile import derive_strategy  # noqa: E402

WIDTH = 74


def rule(char: str = "=") -> str:
    return char * WIDTH


def money(value) -> str:
    return "no disponible" if value is None else f"US$ {value:,.2f}"


def pct(value) -> str:
    return "—" if value is None else f"{value:,.1f} %"


def render(briefing: dict, refresh: dict) -> str:
    out: list[str] = []
    p = briefing["portfolio"]

    out += [rule(), f"BRIEFING DIARIO — {briefing['date']}", rule(), ""]
    out += [briefing["headline"], ""]

    out += ["[1] TU CARTERA", rule("-")]
    if p["total_value"] is None:
        out.append("  No se pudo valorar: faltan precios. No muestro un total parcial")
        out.append("  haciéndolo pasar por completo.")
    else:
        out.append(f"  Valor total ....... {money(p['total_value'])}")
        out.append(f"  Invertido ......... {money(p['invested_value'])}")
        out.append(f"  Efectivo .......... {money(p['cash'])} ({pct(p['cash_pct'])})")
        out.append(f"  En acciones ....... {pct(p['stocks_vs_bonds']['acciones'])}")
        out.append(f"  En bonos .......... {pct(p['stocks_vs_bonds']['bonos'])}")
        out.append(f"  Acciones sueltas .. {pct(p['individual_stock_pct'])}")
        out.append("")
        for pos in p["positions"]:
            price = pos["price"]["formatted"] if pos["price"] else "sin precio"
            out.append(
                f"    {pos['ticker']:<6} {pct(pos['weight_pct']):>8}  {price:>14}  "
                f"{money(pos['unrealized_gain'])}"
            )
    if p["data_warning"]:
        out += ["", f"  AVISO: {p['data_warning']}"]
    out.append("")

    out += [f"[2] ALERTAS SIN LEER ({len(briefing['unread_alerts'])})", rule("-")]
    if not briefing["unread_alerts"]:
        out.append("  Nada pendiente. Un día tranquilo es una buena noticia.")
    for a in briefing["unread_alerts"]:
        out.append(f"  · [{a['kind']}] {a['title']}")
        for datum in a["evidence"]:
            if datum["kind"] == "datapoint":
                out.append(
                    f"      {datum['label']}: {datum['formatted']}  ({datum['citation']})"
                )
    out.append("")

    out += [f"[3] FRENTE A TU ESTRATEGIA ({len(briefing['deviations'])})", rule("-")]
    if not briefing["deviations"]:
        out.append("  Tu cartera sigue alineada con tu plan.")
    for d in briefing["deviations"]:
        out.append(f"  · [{d['kind']}] {d['message']}")
        for datum in d["numbers"]:
            out.append(f"      {datum['label']}: {datum['formatted']}")
    out.append("")

    out += [f"[4] IDEAS QUE ENCAJAN CONTIGO ({len(briefing['ideas'])})", rule("-")]
    if not briefing["ideas"]:
        out.append("  Sin ideas hoy.")
    else:
        out.append(f"  {briefing['ideas_sizing_notice']}")
        out.append("")
    for idea in briefing["ideas"]:
        out.append(f"  {idea['ticker']} — {idea['action_label'].upper()}")
        out.append(f"    {idea['thesis']}")
        sizing = idea["suggested_position"]
        if sizing.get("applies") and sizing.get("amount_usd"):
            out.append(f"    Tamaño sugerido: {money(sizing['amount_usd'])} (alternativa, no se suma)")
        out.append(f"    Riesgo principal: {idea['risks'][0]}")
        out.append(f"    En contra: {idea['counter_argument'][:200]}…")
        out.append(f"    Confianza: {idea['confidence']['level']}")
        out.append("")

    out += ["[5] ESTADO DE LOS DATOS", rule("-")]
    if refresh.get("problems"):
        for problem in refresh["problems"]:
            out.append(f"  · {problem}")
    if not briefing["data_health"] and not refresh.get("problems"):
        out.append("  Todas las fuentes respondieron.")
    for h in briefing["data_health"]:
        out.append(f"  · {h}")
    out.append("")

    out += [rule(), briefing["notices"]["no_rush"], "", briefing["notices"]["read_only"],
            "", briefing["notices"]["not_advice"], rule()]
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Briefing diario en texto (para cron).")
    parser.add_argument("--no-ideas", action="store_true", help="No calcular ideas (más rápido).")
    parser.add_argument("--quiet", action="store_true", help="No imprimir; sólo escribir el archivo.")
    parser.add_argument("--out", default="", help="Ruta del archivo (def: briefing_AAAA-MM-DD.txt).")
    args = parser.parse_args()

    with get_conn() as conn:
        profile = load_profile(conn)
        if profile is None:
            print(
                "No hay perfil configurado todavía. Completa el onboarding en la interfaz "
                "antes de programar la ejecución diaria.",
                file=sys.stderr,
            )
            return 2

        strategy = derive_strategy(profile)
        state = load_portfolio(conn)

        refresh = alerts_core.generate_and_store(conn, profile, strategy, state)
        briefing = build(conn, profile, strategy, state, include_ideas=not args.no_ideas)

    text = render(briefing, refresh)
    out_path = Path(args.out or f"briefing_{date.today().isoformat()}.txt")
    out_path.write_text(text, encoding="utf-8")

    if not args.quiet:
        print(text)
        print(f"\nEscrito en: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
