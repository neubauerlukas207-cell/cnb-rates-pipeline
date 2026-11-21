"""Parsování textových souborů ČNB (denní kurzovní lístek a roční historie).

Formát: hodnoty oddělené `|`, desetinná čárka, kurz platí pro dané *množství* měny (např. 100 JPY).
Roční soubor může v půlce roku změnit hlavičku – když ČNB přidá nebo přestane vyhlašovat měnu
(v roce 2022 zmizel rubl). Parser proto hlavičku čte znovu pokaždé, když na ni narazí.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

_DATE = "%d.%m.%Y"
_CODE = re.compile(r"^[A-Z]{3}$")


class ParseError(ValueError):
    """Soubor nemá očekávaný formát."""


@dataclass(frozen=True, slots=True)
class Rate:
    day: date
    code: str
    amount: int
    rate: Decimal
    """Kurz v Kč za `amount` jednotek měny – přesně (Decimal), jak ho vyhlásila ČNB."""

    @property
    def per_unit(self) -> Decimal:
        """Kurz za 1 jednotku měny (u 100 JPY vydělí stem)."""
        return self.rate / self.amount


def _decimal(text: str, where: str) -> Decimal:
    try:
        value = Decimal(text.strip().replace(",", "."))
    except InvalidOperation as e:
        raise ParseError(f"{where}: neplatné číslo {text!r}") from e
    if value <= 0:
        raise ParseError(f"{where}: kurz musí být kladný, je {value}")
    return value


def _date(text: str, where: str) -> date:
    try:
        return datetime.strptime(text.strip(), _DATE).date()
    except ValueError as e:
        raise ParseError(f"{where}: neplatné datum {text!r}") from e


def parse_daily(text: str) -> tuple[date, list[Rate]]:
    """Denní lístek: 1. řádek „20.11.2026 #223“, 2. hlavička, pak „země|měna|množství|kód|kurz“."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 3:
        raise ParseError("denní lístek je prázdný nebo neúplný")
    day = _date(lines[0].split("#")[0], "řádek 1")
    if lines[1].strip().lower() != "země|měna|množství|kód|kurz":
        raise ParseError(f"řádek 2: neočekávaná hlavička {lines[1]!r}")

    rates = []
    for n, line in enumerate(lines[2:], start=3):
        parts = line.split("|")
        if len(parts) != 5:
            raise ParseError(f"řádek {n}: čekám 5 sloupců, je {len(parts)}")
        _, _, amount, code, rate = parts
        if not _CODE.match(code):
            raise ParseError(f"řádek {n}: neplatný kód měny {code!r}")
        rates.append(Rate(day, code, int(amount), _decimal(rate, f"řádek {n}")))
    return day, rates


def _parse_header(line: str, n: int) -> list[tuple[int, str]]:
    columns = []
    for cell in line.split("|")[1:]:
        match = re.fullmatch(r"(\d+) ([A-Z]{3})", cell.strip())
        if not match:
            raise ParseError(f"řádek {n}: neplatná hlavička sloupce {cell!r}")
        columns.append((int(match[1]), match[2]))
    return columns


def parse_yearly(text: str) -> list[Rate]:
    """Roční historie: hlavička „Datum|1 AUD|…|100 JPY|…“, pak řádek na každý pracovní den."""
    columns: list[tuple[int, str]] | None = None
    rates: list[Rate] = []
    for n, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        if line.startswith("Datum"):
            columns = _parse_header(line, n)
            continue
        if columns is None:
            raise ParseError(f"řádek {n}: data před hlavičkou")
        cells = line.split("|")
        if len(cells) != len(columns) + 1:
            raise ParseError(f"řádek {n}: čekám {len(columns) + 1} sloupců, je {len(cells)}")
        day = _date(cells[0], f"řádek {n}")
        for (amount, code), value in zip(columns, cells[1:], strict=True):
            if value.strip():  # prázdná buňka = kurz ten den nevyhlášen
                rates.append(Rate(day, code, amount, _decimal(value, f"řádek {n}, {code}")))
    return rates
