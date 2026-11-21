"""Statistiky nad historií kurzu."""

from __future__ import annotations

import math
import statistics
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class CurrencyStats:
    code: str
    latest_day: str
    latest: float
    change_1d_pct: float | None
    change_30d_pct: float | None
    change_ytd_pct: float | None
    min_1y: float
    max_1y: float
    volatility_30d_pct: float | None
    """Roční (annualizovaná) volatilita z denních logaritmických výnosů za posledních 30 obchodních dní."""

    def to_dict(self) -> dict:
        return asdict(self)


def _pct(new: Decimal, old: Decimal) -> float:
    return round(float((new - old) / old * 100), 3)


def compute(code: str, series: list[tuple[date, Decimal]]) -> CurrencyStats:
    """`series` = [(den, kurz za 1 jednotku)] seřazená od nejstaršího, aspoň jeden záznam."""
    if not series:
        raise ValueError(f"{code}: žádná data")
    last_day, last = series[-1]
    values = [v for _, v in series]

    def back(n: int) -> Decimal | None:
        return values[-1 - n] if len(values) > n else None

    year_start = next((v for d, v in series if d.year == last_day.year), None)
    prev_year_end = next((v for d, v in reversed(series) if d.year < last_day.year), None)
    ytd_base = prev_year_end or year_start  # proti poslednímu kurzu předchozího roku, jinak prvnímu letošnímu

    last_year = [v for d, v in series if (last_day - d).days <= 365]
    window = values[-31:]  # 31 kurzů = 30 denních změn
    returns = [math.log(float(b / a)) for a, b in zip(window, window[1:], strict=False)]
    volatility = statistics.stdev(returns) * math.sqrt(252) * 100 if len(returns) >= 2 else None

    return CurrencyStats(
        code=code,
        latest_day=last_day.isoformat(),
        latest=round(float(last), 6),
        change_1d_pct=_pct(last, b) if (b := back(1)) is not None else None,
        change_30d_pct=_pct(last, b) if (b := back(30)) is not None else None,
        change_ytd_pct=_pct(last, ytd_base) if ytd_base is not None and len(values) > 1 else None,
        min_1y=round(float(min(last_year)), 6),
        max_1y=round(float(max(last_year)), 6),
        volatility_30d_pct=round(volatility, 2) if volatility is not None else None,
    )
