"""
Tu tesis: por qué compraste algo, y qué te haría dejar de creerlo.

POR QUÉ ESTO ES LO MÁS IMPORTANTE PARA DECIDIR UNA VENTA
--------------------------------------------------------
Sin tesis, la única señal de venta posible es el precio. Y el precio es
precisamente la peor señal: vender porque algo bajó convierte una pérdida
temporal en definitiva, y es el error más común de quien empieza.

Con tesis, la pregunta cambia por completo. Ya no es «¿ha bajado?», sino
«¿sigue siendo cierto lo que me hizo comprar esto?». Esa sí es una razón para
vender, y es la que usan los marcos de inversión a largo plazo.

QUÉ HACE Y QUÉ NO HACE ESTA HERRAMIENTA
---------------------------------------
NO evalúa tu tesis. Es texto libre tuyo y un motor de reglas no puede juzgar si
«creo que su negocio de servicios seguirá creciendo» sigue siendo cierto.
Fingir que sí lo hace sería exactamente el tipo de falsa autoridad que este
producto evita.

Lo que SÍ hace, que es lo útil:
  * Te la pone delante cada vez que revisa la posición, para que la confrontes.
  * Te recuerda cuándo la revisaste por última vez y te avisa si hace mucho.
  * Cuando aparece una señal de deterioro, te pregunta explícitamente si esa
    señal es una de las que tú mismo escribiste como motivo para salir.
  * Si una posición no tiene tesis, lo dice: es un hueco, no un detalle.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional

# A partir de aquí, una tesis lleva demasiado sin mirarse. Seis meses es
# deliberadamente largo: revisar la tesis cada semana invita justo al exceso de
# actividad que la herramienta intenta evitar.
STALE_THESIS_DAYS = 180


@dataclass
class Thesis:
    ticker: str
    text: str
    invalidation: str
    reviewed_at: Optional[date]

    @property
    def exists(self) -> bool:
        return bool(self.text.strip())

    def days_since_review(self, today: Optional[date] = None) -> Optional[int]:
        if self.reviewed_at is None:
            return None
        return ((today or date.today()) - self.reviewed_at).days

    def is_stale(self, today: Optional[date] = None) -> bool:
        days = self.days_since_review(today)
        return days is not None and days > STALE_THESIS_DAYS

    def to_dict(self, today: Optional[date] = None) -> dict:
        return {
            "ticker": self.ticker,
            "exists": self.exists,
            "text": self.text,
            "invalidation": self.invalidation,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "days_since_review": self.days_since_review(today),
            "is_stale": self.is_stale(today),
            "stale_after_days": STALE_THESIS_DAYS,
        }


def _parse_date(value) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def load(conn, ticker: str) -> Thesis:
    row = conn.execute(
        "SELECT thesis, invalidation, thesis_reviewed_at FROM holdings WHERE UPPER(ticker) = ?",
        (ticker.strip().upper(),),
    ).fetchone()
    if row is None:
        return Thesis(ticker.upper(), "", "", None)
    return Thesis(
        ticker=ticker.upper(),
        text=row["thesis"] or "",
        invalidation=row["invalidation"] or "",
        reviewed_at=_parse_date(row["thesis_reviewed_at"]),
    )


def load_all(conn) -> List[Thesis]:
    rows = conn.execute(
        "SELECT ticker, thesis, invalidation, thesis_reviewed_at FROM holdings ORDER BY ticker"
    ).fetchall()
    return [
        Thesis(r["ticker"].upper(), r["thesis"] or "", r["invalidation"] or "",
               _parse_date(r["thesis_reviewed_at"]))
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Cómo se presenta en una recomendación
# ---------------------------------------------------------------------------
def review_prompt(thesis: Thesis, deteriorated: bool, today: Optional[date] = None) -> dict:
    """Qué mostrarle al usuario sobre su tesis en este análisis concreto."""
    if not thesis.exists:
        return {
            "has_thesis": False,
            "headline": "No anotaste por qué compraste esto.",
            "explanation": (
                "Sin eso, lo único que puedo mirar para opinar sobre vender es el precio, "
                "que es justo la peor señal: bajar no significa que la razón por la que "
                "compraste haya dejado de ser cierta. Anota en dos líneas por qué lo "
                "compraste y qué tendría que pasar para que dejaras de creerlo."
            ),
            "question": None,
            "stale": False,
        }

    days = thesis.days_since_review(today)
    if deteriorated and thesis.invalidation.strip():
        question = (
            "Hay señales de deterioro. Escribiste que dejarías de creer en esta idea si "
            f"pasara esto: «{thesis.invalidation.strip()}». ¿Ha pasado? Si la respuesta es "
            "no, lo que ves es ruido, no un motivo para vender."
        )
    elif deteriorated:
        question = (
            "Hay señales de deterioro. No anotaste qué te haría cambiar de idea, así que "
            "esta es una buena ocasión para hacerlo: ¿lo que está pasando contradice la "
            "razón por la que compraste?"
        )
    else:
        question = (
            "¿Sigue siendo cierto lo que escribiste? Si la respuesta es sí, no hay nada "
            "que hacer, por mucho que el precio se haya movido."
        )

    return {
        "has_thesis": True,
        "headline": "Esto escribiste cuando la compraste:",
        "thesis": thesis.text.strip(),
        "invalidation": thesis.invalidation.strip(),
        "reviewed_at": thesis.reviewed_at.isoformat() if thesis.reviewed_at else None,
        "days_since_review": days,
        "stale": thesis.is_stale(today),
        "explanation": (
            "La herramienta no juzga tu tesis: es tuya y es texto libre. Lo que hace es "
            "ponértela delante para que decidas tú, que es lo que de verdad debería mover "
            "una venta."
        ),
        "question": question,
    }


def missing_thesis_warning(theses: List[Thesis]) -> Optional[str]:
    faltan = [t.ticker for t in theses if not t.exists]
    if not faltan:
        return None
    return (
        "No has anotado por qué compraste: " + ", ".join(faltan) + ". "
        "Sin esa nota, lo único que puedo mirar para opinar sobre vender es el precio, "
        "y el precio es la peor de las señales posibles."
    )


def stale_thesis_warning(theses: List[Thesis], today: Optional[date] = None) -> Optional[str]:
    viejas = [t.ticker for t in theses if t.exists and t.is_stale(today)]
    if not viejas:
        return None
    return (
        "Hace tiempo que no revisas tu tesis de: " + ", ".join(viejas) + ". "
        "Vale la pena releerla con calma cuando tengas un rato y comprobar si sigue en pie. "
        "No hay ninguna prisa."
    )
