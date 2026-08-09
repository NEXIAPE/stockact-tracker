"""Esquemas de entrada de la API (validación con Pydantic)."""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

RISK = ("conservador", "moderado", "agresivo")
EXPERIENCE = ("principiante", "intermedio", "avanzado")
ASSET_TYPES = ("accion", "etf")


class ProfileIn(BaseModel):
    initial_capital: float = Field(ge=0, description="Cuánto vas a invertir para empezar (USD)")
    monthly_contribution: float = Field(default=0, ge=0, description="Aporte mensual (USD)")
    risk_tolerance: str
    horizon_years: int = Field(ge=1, le=60)
    goals: List[str] = Field(default_factory=list)
    experience: str = "principiante"
    base_currency: str = "USD"
    emergency_fund_ok: bool = False
    notes: str = ""

    @field_validator("risk_tolerance")
    @classmethod
    def _risk(cls, v: str) -> str:
        if v not in RISK:
            raise ValueError(f"risk_tolerance debe ser uno de {RISK}")
        return v

    @field_validator("experience")
    @classmethod
    def _exp(cls, v: str) -> str:
        if v not in EXPERIENCE:
            raise ValueError(f"experience debe ser uno de {EXPERIENCE}")
        return v


class HoldingIn(BaseModel):
    ticker: str
    shares: float = Field(gt=0)
    avg_cost: float = Field(ge=0, description="Coste medio por acción, en USD")
    asset_type: Optional[str] = None
    notes: str = ""
    # Tu tesis. Opcional para no bloquear el registro, pero la herramienta avisa
    # si falta: sin ella, opinar sobre vender solo puede apoyarse en el precio.
    thesis: str = Field(default="", description="Por qué compraste esto")
    invalidation: str = Field(
        default="", description="Qué tendría que pasar para que dejaras de creerlo"
    )

    @field_validator("ticker")
    @classmethod
    def _ticker(cls, v: str) -> str:
        v = v.strip().upper()
        if not v or len(v) > 12:
            raise ValueError("Ticker no válido")
        return v

    @field_validator("asset_type")
    @classmethod
    def _atype(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ASSET_TYPES:
            raise ValueError(f"asset_type debe ser uno de {ASSET_TYPES}")
        return v


class CashIn(BaseModel):
    amount: float = Field(ge=0, description="Efectivo sin invertir, en USD")


class TradeIn(BaseModel):
    """Bitácora de una operación que TÚ ya ejecutaste en tu bróker.

    Esto es un registro histórico. La herramienta no envía ni ha enviado nada:
    tú operas a mano y luego lo anotas aquí.
    """

    ticker: str
    action: str
    shares: float = Field(gt=0)
    price: float = Field(gt=0)
    traded_on: date
    notes: str = ""

    @field_validator("action")
    @classmethod
    def _action(cls, v: str) -> str:
        if v not in ("compra", "venta"):
            raise ValueError("action debe ser 'compra' o 'venta'")
        return v

    @field_validator("ticker")
    @classmethod
    def _ticker(cls, v: str) -> str:
        return v.strip().upper()


class WatchIn(BaseModel):
    ticker: str
    asset_type: Optional[str] = None
    reason: str = ""
    target_buy_price: Optional[float] = Field(default=None, gt=0)
    max_drawdown_pct: Optional[float] = Field(default=None, gt=0, le=99)

    @field_validator("ticker")
    @classmethod
    def _ticker(cls, v: str) -> str:
        v = v.strip().upper()
        if not v or len(v) > 12:
            raise ValueError("Ticker no válido")
        return v


class UserFactIn(BaseModel):
    """Un dato que leíste en una fuente oficial y quieres que quede citado."""

    key: str = Field(description="Identificador del dato, p. ej. 'expense_ratio'")
    value: float
    unit: str = "%"
    source_label: str = "Ficha oficial del emisor"
    source_url: str = ""
    as_of: date = Field(description="Fecha en que LEÍSTE el dato en la fuente")

    @field_validator("key")
    @classmethod
    def _key(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("key requerido")
        return v


class ThesisIn(BaseModel):
    """Anotar o revisar la tesis de una posición que ya tienes."""

    thesis: str = ""
    invalidation: str = ""
    mark_reviewed: bool = Field(
        default=True,
        description="Marca la tesis como revisada hoy (para saber cuándo la miraste)",
    )
