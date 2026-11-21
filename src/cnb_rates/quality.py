"""Kontroly kvality dat – pipeline selže dřív, než by publikovala nesmysly."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from . import db


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def check(conn: sqlite3.Connection, today: date, min_currencies: int = 25, max_jump_pct: float = 15.0) -> Report:
    report = Report()
    all_days = db.days(conn)
    if not all_days:
        report.errors.append("databáze je prázdná")
        return report

    # 1) čerstvost: ČNB vyhlašuje v pracovní dny, i přes svátky by data neměla být starší než týden
    if (today - all_days[-1]).days > 7:
        report.errors.append(f"poslední kurz je z {all_days[-1]}, data jsou zastaralá")

    # 2) díry v řadě – Vánoce (svátky + víkend) dají až 6 dní bez kurzu, víc už je podezřelé
    for a, b in zip(all_days, all_days[1:], strict=False):
        if b - a > timedelta(days=6):
            report.warnings.append(f"mezera v datech mezi {a} a {b}")

    # 3) úplnost posledního dne
    latest = db.currencies(conn)
    if len(latest) < min_currencies:
        report.errors.append(f"poslední den má jen {len(latest)} měn (čekám aspoň {min_currencies})")
    for required in ("EUR", "USD"):
        if required not in latest:
            report.errors.append(f"chybí kurz {required}")

    # 4) nepravděpodobné skoky (překlep ve zdroji, chybné množství)
    for code in latest:
        series = db.history(conn, code)
        for (d1, v1), (d2, v2) in zip(series, series[1:], strict=False):
            jump = abs(v2 - v1) / v1 * 100
            if jump > Decimal(max_jump_pct):
                report.warnings.append(f"{code}: skok {jump:.1f} % mezi {d1} a {d2}")
    return report
