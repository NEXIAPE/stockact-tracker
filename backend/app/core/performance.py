"""
Cómo te está yendo de verdad, y la comparación que casi nadie quiere hacer.

LA PREGUNTA QUE IMPORTA
-----------------------
No es «¿he ganado dinero?». Casi cualquiera gana dinero en un mercado que sube.
La pregunta es: **¿me habría ido mejor comprando un fondo amplio y no volviendo
a mirar?** Si la respuesta es que no, toda la molestia de elegir activos no está
pagando, y saberlo a tiempo vale más que cualquier idea de compra.

CÓMO SE COMPARA, Y POR QUÉ ASÍ
------------------------------
Comparar rentabilidades a secas sería tramposo: tú no invertiste todo el dinero
el mismo día. Lo que se hace aquí es reconstruir la alternativa honesta: **las
mismas cantidades, en las mismas fechas, puestas en un fondo de referencia**.
Eso responde a «¿qué habría pasado si en vez de esto hubiera comprado el índice?»,
que es la comparación justa.

Se calcula sobre tu bitácora de operaciones. Si no has registrado operaciones,
se dice claramente que no se puede comparar, en vez de inventar una cifra a
partir del coste medio (que perdería las fechas y falsearía el resultado).

TODO NÚMERO DE AQUÍ VA CITADO
-----------------------------
Los aportes salen de lo que tú registraste ("Tus datos"); los precios del
proveedor real, con su fecha. Lo calculado se declara como calculado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

from ..providers import prices
from ..providers.http import FetchError
from .datapoint import DataPoint, Datum, Missing, Source, derived_source, user_source
from .portfolio import PortfolioState

# Referencia por defecto: acciones de todo el mundo en un solo fondo. Es el
# listón honesto para una cartera diversificada; comparar contra el S&P 500
# favorece o castiga según la moda del año.
DEFAULT_BENCHMARK = "VT"


@dataclass
class Trade:
    ticker: str
    action: str        # compra | venta
    shares: float
    price: float
    day: date

    @property
    def cash_flow(self) -> float:
        """Positivo = dinero que metiste; negativo = dinero que sacaste."""
        amount = self.shares * self.price
        return amount if self.action == "compra" else -amount


@dataclass
class Performance:
    contributed: float                  # dinero neto que has metido
    current_value: Optional[float]      # lo que vale hoy (None si faltan precios)
    first_trade: Optional[date]
    trades: int
    benchmark_ticker: str
    benchmark_value: Optional[float]    # lo mismo, puesto en el índice
    benchmark_error: str = ""
    notes: List[str] = field(default_factory=list)
    # Si la bitácora no cubre todas tus posiciones, la comparación es INVÁLIDA:
    # enfrentaría el valor completo de la cartera contra sólo una parte de lo
    # aportado, y saldría un resultado espectacular que no es real.
    uncovered: List[str] = field(default_factory=list)

    @property
    def comparable(self) -> bool:
        return bool(self.trades) and not self.uncovered

    @property
    def gain(self) -> Optional[float]:
        if self.current_value is None or not self.comparable:
            return None
        return self.current_value - self.contributed

    @property
    def gain_pct(self) -> Optional[float]:
        if self.current_value is None or self.contributed <= 0 or not self.comparable:
            return None
        return (self.current_value / self.contributed - 1.0) * 100.0

    @property
    def benchmark_gain_pct(self) -> Optional[float]:
        if self.benchmark_value is None or self.contributed <= 0 or not self.comparable:
            return None
        return (self.benchmark_value / self.contributed - 1.0) * 100.0

    @property
    def difference_pct(self) -> Optional[float]:
        a, b = self.gain_pct, self.benchmark_gain_pct
        return None if a is None or b is None else a - b


def load_trades(conn) -> List[Trade]:
    rows = conn.execute(
        "SELECT ticker, action, shares, price, traded_on FROM trade_log ORDER BY traded_on"
    ).fetchall()
    out: List[Trade] = []
    for r in rows:
        try:
            out.append(Trade(r["ticker"].upper(), r["action"], float(r["shares"]),
                             float(r["price"]), date.fromisoformat(r["traded_on"][:10])))
        except (ValueError, TypeError):
            continue  # fila corrupta: se ignora, no se adivina
    return out


def _close_on_or_after(series, day: date) -> Optional[float]:
    """Cierre del primer día con cotización a partir de ``day``.

    Las operaciones caen en fines de semana y festivos; buscar el siguiente día
    hábil es correcto. Inventar un precio interpolado no lo sería.
    """
    for bar in series.bars:
        if bar.day >= day:
            return bar.close
    return None


def compute(
    conn,
    state: PortfolioState,
    benchmark: str = DEFAULT_BENCHMARK,
    today: Optional[date] = None,
) -> Performance:
    today = today or date.today()
    trades = load_trades(conn)

    contributed = sum(t.cash_flow for t in trades)
    notes: List[str] = []

    # ¿Cubre la bitácora todo lo que tienes? Si no, comparar sería engañarte a
    # tu favor: el valor de una posición no registrada cuenta como ganancia
    # porque su coste nunca entró en los aportes.
    en_bitacora = {t.ticker for t in trades}
    uncovered = sorted({p.ticker for p in state.positions} - en_bitacora)
    if uncovered and trades:
        notes.append(
            "Tu bitácora no incluye operaciones de: " + ", ".join(uncovered) + ". "
            "Sin ellas la comparación saldría a tu favor sin motivo, porque el valor de "
            "esas posiciones contaría como ganancia mientras que lo que pagaste por ellas "
            "no cuenta como aporte. Añádelas a la bitácora y el cálculo será real."
        )

    if not trades:
        return Performance(
            contributed=0.0, current_value=state.invested_value, first_trade=None,
            trades=0, benchmark_ticker=benchmark.upper(), benchmark_value=None,
            benchmark_error="",
            notes=[
                "No has registrado operaciones en la bitácora, así que no puedo comparar tu "
                "resultado con nada. La comparación necesita saber CUÁNTO pusiste y CUÁNDO: "
                "con sólo el coste medio se perderían las fechas y el resultado sería falso."
            ],
        )

    # La alternativa honesta: los mismos importes, los mismos días, en el índice.
    benchmark_value: Optional[float] = None
    benchmark_error = ""
    try:
        serie = prices.fetch_daily(benchmark)
        precio_hoy = serie.last.close
        participaciones = 0.0
        sin_precio: List[str] = []
        for t in trades:
            precio = _close_on_or_after(serie, t.day)
            if precio is None or precio <= 0:
                sin_precio.append(t.day.isoformat())
                continue
            participaciones += t.cash_flow / precio
        benchmark_value = participaciones * precio_hoy
        if sin_precio:
            notes.append(
                f"El índice de referencia no tiene cotización para estas fechas: "
                f"{', '.join(sorted(set(sin_precio)))}. Esas operaciones quedan fuera de la "
                f"comparación, que por tanto es aproximada."
            )
    except FetchError as exc:
        benchmark_error = str(exc)
        notes.append(
            f"No se pudo obtener el histórico de {benchmark.upper()} para comparar: {exc}"
        )

    if state.missing_prices:
        notes.append(
            "Faltan precios de " + ", ".join(state.missing_prices) +
            ", así que el valor actual de tu cartera está incompleto y la comparación "
            "sale peor de lo que es en realidad."
        )

    return Performance(
        contributed=contributed,
        current_value=state.invested_value,
        first_trade=trades[0].day,
        trades=len(trades),
        benchmark_ticker=benchmark.upper(),
        benchmark_value=benchmark_value,
        benchmark_error=benchmark_error,
        notes=notes,
        uncovered=uncovered,
    )


def verdict(perf: Performance) -> str:
    """La lectura en una frase, sin cifras (las cifras van citadas aparte)."""
    if perf.uncovered:
        return (
            "No puedo comparar todavía, y prefiero decírtelo a darte una cifra halagüeña "
            "que sería falsa: faltan en tu bitácora las operaciones de " +
            ", ".join(perf.uncovered) + ". Mientras falten, el valor de esas posiciones "
            "contaría como ganancia salida de la nada."
        )

    diff = perf.difference_pct
    if diff is None:
        return (
            "Todavía no se puede comparar tu resultado con el de un fondo amplio. "
            "Registra tus operaciones en la bitácora y podré hacerlo."
        )
    if perf.trades < 5 or (perf.first_trade and (date.today() - perf.first_trade).days < 365):
        return (
            "Llevas demasiado poco tiempo o demasiadas pocas operaciones para que esta "
            "comparación signifique algo. A menos de un año, casi todo es suerte: no "
            "saques conclusiones ni para bien ni para mal."
        )
    if diff > 2:
        return (
            "Vas por delante del fondo de referencia. Merece la pena recordar que unos "
            "pocos años por delante no demuestran habilidad: gestores profesionales baten "
            "al índice durante rachas largas y luego dejan de hacerlo."
        )
    if diff < -2:
        return (
            "Vas por detrás de lo que habrías conseguido poniendo el mismo dinero, los "
            "mismos días, en un fondo amplio. No es un fracaso ni obliga a cambiar nada "
            "hoy, pero sí es la señal más honesta de que elegir activos te está costando "
            "en vez de aportarte."
        )
    return (
        "Vas prácticamente igual que el fondo de referencia. Conviene preguntarse si el "
        "tiempo y la atención que dedicas a elegir compensan frente a comprar un fondo "
        "amplio y no volver a mirar."
    )


def to_dict(perf: Performance, today: Optional[date] = None) -> dict:
    today = today or date.today()
    src = user_source()
    datos: List[Datum] = []

    # SI LA COMPARACIÓN NO ES VÁLIDA, TAMPOCO SE ENSEÑAN SUS INGREDIENTES.
    #
    # Antes se bloqueaban los porcentajes pero se mostraban igual «aportado» y
    # «valor actual» uno al lado del otro. Cualquiera divide esas dos cifras y
    # saca exactamente el resultado engañoso que el bloqueo pretendía evitar
    # (en pruebas: un +114 % completamente falso). Ocultar la conclusión y
    # servir los ingredientes no es honestidad, es disimulo.
    if not perf.comparable:
        if perf.uncovered:
            datos.append(Missing(
                label="Comparación con un fondo amplio",
                reason=(
                    "Faltan en tu bitácora las operaciones de "
                    + ", ".join(perf.uncovered)
                    + ". Con la bitácora incompleta cualquier cifra saldría a tu favor sin "
                    "motivo, así que no se muestra ninguna."
                ),
                tried="Tu bitácora de operaciones",
            ))
        else:
            datos.append(Missing(
                label="Comparación con un fondo amplio",
                reason=(
                    "No has registrado operaciones. La comparación necesita saber cuánto "
                    "pusiste y cuándo."
                ),
                tried="Tu bitácora de operaciones",
            ))
        return {
            "comparable": False,
            "uncovered": perf.uncovered,
            "contributed": None, "current_value": None, "gain": None, "gain_pct": None,
            "benchmark_ticker": perf.benchmark_ticker, "benchmark_value": None,
            "benchmark_gain_pct": None, "difference_pct": None,
            "trades": perf.trades,
            "first_trade": perf.first_trade.isoformat() if perf.first_trade else None,
            "verdict": verdict(perf),
            "data": [d.to_dict(today) for d in datos],
            "notes": perf.notes,
            "method": (
                "La comparación reconstruye qué habría pasado si cada aporte que registraste "
                "hubiera ido, ese mismo día, a un fondo amplio de referencia."
            ),
        }

    datos.append(DataPoint(
        label="Dinero neto que has aportado", value=perf.contributed, unit="USD",
        as_of=today, source=src,
    ))
    if perf.current_value is not None:
        datos.append(DataPoint(
            label="Valor actual de tu cartera", value=perf.current_value, unit="USD",
            as_of=today,
            source=derived_source([Source(name="Proveedor de precios")], "participaciones × cierre"),
        ))
    else:
        datos.append(Missing(
            label="Valor actual de tu cartera",
            reason="Faltan precios de alguna posición, así que el total sería engañoso.",
        ))

    if perf.benchmark_value is not None:
        datos.append(DataPoint(
            label=f"Lo mismo, puesto en {perf.benchmark_ticker}",
            value=perf.benchmark_value, unit="USD", as_of=today,
            source=derived_source(
                [Source(name="Proveedor de precios")],
                f"tus mismos importes en sus mismas fechas, comprando {perf.benchmark_ticker}",
            ),
        ))
    else:
        datos.append(Missing(
            label=f"Lo mismo, puesto en {perf.benchmark_ticker}",
            reason=perf.benchmark_error or "No se pudo obtener el histórico del índice.",
        ))

    return {
        "comparable": perf.comparable,
        "uncovered": perf.uncovered,
        "contributed": round(perf.contributed, 2) if perf.trades else None,
        "current_value": round(perf.current_value, 2) if perf.current_value is not None else None,
        "gain": round(perf.gain, 2) if perf.gain is not None else None,
        "gain_pct": round(perf.gain_pct, 2) if perf.gain_pct is not None else None,
        "benchmark_ticker": perf.benchmark_ticker,
        "benchmark_value": round(perf.benchmark_value, 2) if perf.benchmark_value is not None else None,
        "benchmark_gain_pct": round(perf.benchmark_gain_pct, 2) if perf.benchmark_gain_pct is not None else None,
        "difference_pct": round(perf.difference_pct, 2) if perf.difference_pct is not None else None,
        "trades": perf.trades,
        "first_trade": perf.first_trade.isoformat() if perf.first_trade else None,
        "verdict": verdict(perf),
        "data": [d.to_dict(today) for d in datos],
        "notes": perf.notes,
        "method": (
            "La comparación reconstruye qué habría pasado si cada aporte que registraste "
            "hubiera ido, ese mismo día, a un fondo amplio de referencia. Comparar "
            "rentabilidades a secas sería tramposo porque no invertiste todo el mismo día."
        ),
    }
