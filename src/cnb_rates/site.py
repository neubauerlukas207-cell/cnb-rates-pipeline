"""Sestavení statického dashboardu: šablona ze složky site/ + vygenerovaný data.json."""

from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path

from . import db
from .stats import compute

# měny, které dashboard ukáže jako první
FEATURED = ["EUR", "USD", "GBP", "CHF", "PLN", "JPY"]


def build_data(conn: sqlite3.Connection, history_days: int = 400) -> dict:
    codes = db.currencies(conn)
    ordered = [c for c in FEATURED if c in codes] + [c for c in codes if c not in FEATURED]
    currencies = []
    for code in ordered:
        series = db.history(conn, code)
        stats = compute(code, series)
        recent = series[-history_days:]
        currencies.append({
            **stats.to_dict(),
            "history": [[d.isoformat(), round(float(v), 6)] for d, v in recent],
        })
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": "Česká národní banka – kurzy devizového trhu",
        "latest_day": currencies[0]["latest_day"] if currencies else None,
        "currencies": currencies,
    }


def build_site(conn: sqlite3.Connection, out: Path) -> Path:
    """Zkopíruje šablonu dashboardu do `out` a vedle ní uloží data.json."""
    template = resources.files("cnb_rates") / "site"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for item in template.iterdir():
        if item.is_file():
            (out / item.name).write_bytes(item.read_bytes())
    data = build_data(conn)
    (out / "data.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return out / "data.json"
