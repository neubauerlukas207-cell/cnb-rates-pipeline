"""Úložiště v SQLite. Zápis je idempotentní – opakované spuštění pipeline nic nezdvojí."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from pathlib import Path

from .parse import Rate

SCHEMA = """
CREATE TABLE IF NOT EXISTS rates (
    day     TEXT    NOT NULL,           -- ISO datum YYYY-MM-DD (řadí se správně i jako text)
    code    TEXT    NOT NULL,
    amount  INTEGER NOT NULL CHECK (amount > 0),
    rate    TEXT    NOT NULL,           -- Decimal jako text: přesná hodnota od ČNB, žádné zaokrouhlení floatu
    PRIMARY KEY (day, code)
);
CREATE INDEX IF NOT EXISTS idx_rates_code_day ON rates (code, day);
"""


def connect(path: Path | str) -> sqlite3.Connection:
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


def upsert(conn: sqlite3.Connection, rates: Iterable[Rate]) -> int:
    """Vloží nebo přepíše kurzy (ČNB občas opraví vyhlášený kurz). Vrátí počet zpracovaných řádků."""
    rows = [(r.day.isoformat(), r.code, r.amount, str(r.rate)) for r in rates]
    with conn:  # jedna transakce – buď vše, nebo nic
        conn.executemany(
            """INSERT INTO rates (day, code, amount, rate) VALUES (?, ?, ?, ?)
               ON CONFLICT (day, code) DO UPDATE SET amount = excluded.amount, rate = excluded.rate""",
            rows,
        )
    return len(rows)


def history(conn: sqlite3.Connection, code: str) -> list[tuple[date, Decimal]]:
    """Kurz za 1 jednotku měny v čase, seřazeno od nejstaršího."""
    rows = conn.execute("SELECT day, amount, rate FROM rates WHERE code = ? ORDER BY day", (code,)).fetchall()
    return [(date.fromisoformat(d), Decimal(r) / a) for d, a, r in rows]


def currencies(conn: sqlite3.Connection) -> list[str]:
    """Měny, které mají kurz v posledním dni (vyřazené měny jako RUB vynechá)."""
    return [c for (c,) in conn.execute(
        "SELECT code FROM rates WHERE day = (SELECT MAX(day) FROM rates) ORDER BY code")]


def days(conn: sqlite3.Connection) -> list[date]:
    return [date.fromisoformat(d) for (d,) in conn.execute("SELECT DISTINCT day FROM rates ORDER BY day")]
