"""
Dato citado: la unidad atómica de todo número que la herramienta muestra.

REGLA DURA #1 del producto: nunca se muestra un número sin fuente y fecha.

Para hacer cumplir esa regla en código (y no sólo por buena voluntad), ningún
número viaja "suelto" por la aplicación. Todo valor numérico se envuelve en un
``DataPoint`` que obliga a declarar:

  * de dónde salió (``source``),
  * a qué fecha se refiere el dato (``as_of``),
  * cuándo lo consultamos (``retrieved_at``).

Cuando un dato NO existe, NO se rellena con cero ni se omite en silencio: se
devuelve un ``Missing`` que explica por qué falta. El frontend lo pinta como
"no disponible" y el motor de recomendación baja la confianza en consecuencia.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Iterable, Optional, Union


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Source:
    """Procedencia de un dato. ``url`` puede ser vacía sólo para datos que el
    propio usuario introdujo (su cartera, su perfil), donde la "fuente" es él.
    """

    name: str            # "Stooq", "SEC EDGAR", "Finnhub", "Tus datos"
    url: str = ""
    retrieved_at: datetime = field(default_factory=utcnow)

    def cite(self) -> str:
        return f"{self.name}, consultado {self.retrieved_at.date().isoformat()}"


# Fuentes de datos que introduce el propio usuario. Son "reales" (no
# inventadas por la herramienta) y por eso pueden citarse.
def user_source(retrieved_at: Optional[datetime] = None) -> Source:
    return Source(name="Tus datos", url="", retrieved_at=retrieved_at or utcnow())


def derived_source(base: Iterable[Source], method: str) -> Source:
    """Fuente de un valor CALCULADO a partir de otros datos citados.

    Un cálculo propio (una media móvil, un margen) no es un dato inventado
    siempre que se declare el método y las fuentes de entrada. Eso es lo que
    representa esta fuente derivada.
    """
    names = sorted({s.name for s in base})
    newest = max((s.retrieved_at for s in base), default=utcnow())
    return Source(
        name=f"Calculado por la herramienta ({method}) sobre {', '.join(names)}",
        url="",
        retrieved_at=newest,
    )


Number = Union[int, float]


@dataclass(frozen=True)
class DataPoint:
    """Un número (o texto corto) con su cita obligatoria."""

    label: str           # "Precio de cierre", "Margen neto"
    value: Number
    unit: str            # "USD", "%", "x", "días", "acciones"
    as_of: date          # fecha A LA QUE SE REFIERE el dato
    source: Source
    precision: int = 2

    # ---- Presentación ----------------------------------------------------
    def formatted(self) -> str:
        v = self.value
        if isinstance(v, float):
            text = f"{v:,.{self.precision}f}"
        else:
            text = f"{v:,}"
        if self.unit == "USD":
            return f"US$ {text}"
        if self.unit == "%":
            return f"{text} %"
        if self.unit == "x":
            return f"{text}x"
        return f"{text} {self.unit}".strip()

    def citation(self) -> str:
        return f"{self.source.name} — dato al {self.as_of.isoformat()}"

    def age_days(self, today: Optional[date] = None) -> int:
        return ((today or date.today()) - self.as_of).days

    def to_dict(self, today: Optional[date] = None) -> dict:
        return {
            "kind": "datapoint",
            "label": self.label,
            "value": self.value,
            "unit": self.unit,
            "formatted": self.formatted(),
            "as_of": self.as_of.isoformat(),
            "age_days": self.age_days(today),
            "source_name": self.source.name,
            "source_url": self.source.url,
            "retrieved_at": self.source.retrieved_at.isoformat(),
            "citation": self.citation(),
        }

    def numeric_tokens(self) -> set[str]:
        """Representaciones textuales admisibles de este número.

        El guardián anti-invención (``core.guards``) usa este conjunto para
        comprobar que cualquier cifra que aparezca en la prosa proviene de un
        dato citado y no de la imaginación de una plantilla.
        """
        tokens: set[str] = set()
        v = self.value
        if isinstance(v, (int, float)):
            for p in (0, 1, 2, 3):
                tokens.add(f"{v:,.{p}f}")
                tokens.add(f"{v:.{p}f}")
            tokens.add(str(v))
            if float(v).is_integer():
                tokens.add(str(int(v)))
                tokens.add(f"{int(v):,}")
        tokens.add(self.as_of.isoformat())
        tokens.add(str(self.as_of.year))
        return {t for t in tokens if t}


@dataclass(frozen=True)
class Missing:
    """Un dato que NO tenemos. Se muestra explícitamente como faltante."""

    label: str
    reason: str          # "El proveedor no cubre ETFs", "Sin cobertura para este ticker"
    tried: str = ""      # qué fuentes se intentaron

    def to_dict(self, today: Optional[date] = None) -> dict:
        return {
            "kind": "missing",
            "label": self.label,
            "reason": self.reason,
            "tried": self.tried,
        }


Datum = Union[DataPoint, Missing]


def is_present(d: Optional[Datum]) -> bool:
    return isinstance(d, DataPoint)


def value_or_none(d: Optional[Datum]) -> Optional[Number]:
    return d.value if isinstance(d, DataPoint) else None


def serialize(d: Optional[Datum], today: Optional[date] = None) -> Optional[dict]:
    if d is None:
        return None
    return d.to_dict(today)
