"""Příkazová řádka pipeline.

    cnb-rates update --years 2025 2026      # stáhne roční historie + dnešní lístek do SQLite
    cnb-rates check                         # kontrola kvality dat
    cnb-rates build-site --out public       # statický dashboard
    cnb-rates run --out public              # vše výše najednou (používá CI)
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from . import db, quality
from .fetch import CnbClient
from .site import build_site

log = logging.getLogger("cnb_rates")


def update(conn, client: CnbClient, years: list[int]) -> int:
    total = 0
    for year in years:
        rates = client.year(year)
        total += db.upsert(conn, rates)
        log.info("rok %s: %s kurzů", year, len(rates))
    day, rates = client.daily()  # dnešní lístek – roční soubor se aktualizuje se zpožděním
    total += db.upsert(conn, rates)
    log.info("denní lístek %s: %s kurzů", day, len(rates))
    return total


def run_check(conn, today: date) -> bool:
    report = quality.check(conn, today)
    for w in report.warnings:
        log.warning("kvalita: %s", w)
    for e in report.errors:
        log.error("kvalita: %s", e)
    return report.ok


def main(argv: list[str] | None = None, client: CnbClient | None = None, today: date | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cnb-rates", description="Pipeline kurzů ČNB")
    parser.add_argument("--db", type=Path, default=Path("data/rates.db"))
    sub = parser.add_subparsers(dest="command", required=True)
    p_update = sub.add_parser("update")
    p_update.add_argument("--years", type=int, nargs="+")
    sub.add_parser("check")
    p_site = sub.add_parser("build-site")
    p_site.add_argument("--out", type=Path, default=Path("public"))
    p_run = sub.add_parser("run")
    p_run.add_argument("--out", type=Path, default=Path("public"))
    p_run.add_argument("--years", type=int, nargs="+")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    today = today or date.today()
    years = getattr(args, "years", None) or [today.year - 1, today.year]
    client = client or CnbClient()
    conn = db.connect(args.db)

    if args.command in ("update", "run"):
        log.info("uloženo %s záznamů", update(conn, client, years))
    if args.command in ("check", "run") and not run_check(conn, today):
        log.error("kontrola kvality selhala – web se nepublikuje")
        return 1
    if args.command in ("build-site", "run"):
        path = build_site(conn, args.out)
        log.info("dashboard: %s", path.parent)
    return 0


if __name__ == "__main__":
    sys.exit(main())
