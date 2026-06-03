"""
Generación del informe diario en TEXTO.

Contenido:
  * Divulgaciones nuevas detectadas en esta ejecución.
  * Top 10 tickers de los últimos 30 días.
  * Desglose por sector.

IMPORTANTE: el informe es DESCRIPTIVO. No emite recomendaciones de inversión ni
juicios; sólo resume datos públicos ya divulgados.
"""

from __future__ import annotations

from datetime import date
from typing import List

from models import Disclosure
from storage import Storage


DISCLAIMER = (
    "AVISO: Informe meramente descriptivo de divulgaciones públicas (STOCK Act). "
    "NO es asesoramiento financiero ni una recomendación de compra/venta. Los "
    "datos pueden tener un desfase de hasta ~45 dias respecto a la operacion."
)


def build_report(
    storage: Storage,
    new_disclosures: List[Disclosure],
    today: date | None = None,
    days: int = 30,
) -> str:
    today = today or date.today()
    lines: List[str] = []

    lines.append("=" * 70)
    lines.append(f"INFORME DIARIO STOCK Act  -  {today.isoformat()}")
    lines.append("=" * 70)
    lines.append("")
    lines.append(DISCLAIMER)
    lines.append("")

    # --- Novedades ---------------------------------------------------------
    lines.append(f"[1] DIVULGACIONES NUEVAS ({len(new_disclosures)})")
    lines.append("-" * 70)
    if not new_disclosures:
        lines.append("  (Sin novedades en esta ejecucion.)")
    else:
        for d in sorted(new_disclosures, key=lambda x: (str(x.transaction_date or ""), x.ticker)):
            tag = " [ENMIENDA]" if d.is_amendment else ""
            lines.append(
                f"  - {d.transaction_date}  {d.filer_name}  "
                f"{d.ticker or '(s/ticker)'}  {d.transaction_type}  "
                f"{d.amount_range}  [{d.source}]{tag}"
            )
    lines.append("")

    # --- Top tickers -------------------------------------------------------
    lines.append(f"[2] TOP 10 TICKERS (ultimos {days} dias, por nº de transacciones)")
    lines.append("-" * 70)
    top = storage.top_tickers(days=days, limit=10, today=today)
    if not top:
        lines.append("  (Sin datos en la ventana.)")
    else:
        for rank, (ticker, n) in enumerate(top, start=1):
            lines.append(f"  {rank:>2}. {ticker:<8} {n} transaccion(es)")
    lines.append("")

    # --- Desglose por sector ----------------------------------------------
    lines.append(f"[3] DESGLOSE POR SECTOR (ultimos {days} dias)")
    lines.append("-" * 70)
    sectors = storage.sector_breakdown(days=days, today=today)
    if not sectors:
        lines.append("  (Sin datos en la ventana.)")
    else:
        total = sum(n for _, n in sectors)
        for sector, n in sectors:
            pct = (100.0 * n / total) if total else 0.0
            lines.append(f"  {sector:<24} {n:>4}  ({pct:5.1f}%)")
    lines.append("")
    lines.append("=" * 70)
    lines.append("Fin del informe. Datos de fuentes oficiales de divulgacion publica.")
    lines.append("=" * 70)

    return "\n".join(lines)
