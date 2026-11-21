from datetime import date, timedelta
from decimal import Decimal

from cnb_rates import db, quality
from cnb_rates.parse import Rate, parse_yearly


def loaded(text: str):
    conn = db.connect(":memory:")
    db.upsert(conn, parse_yearly(text))
    return conn


def test_cerstva_a_uplna_data_projdou(yearly_text):
    report = quality.check(loaded(yearly_text), today=date(2026, 3, 1))
    assert report.ok, report.errors


def test_prazdna_databaze():
    assert quality.check(db.connect(":memory:"), today=date(2026, 3, 1)).errors == ["databáze je prázdná"]


def test_zastarala_data(yearly_text):
    report = quality.check(loaded(yearly_text), today=date(2026, 6, 1))
    assert any("zastaralá" in e for e in report.errors)


def test_malo_men_a_chybejici_eur():
    conn = db.connect(":memory:")
    db.upsert(conn, [Rate(date(2026, 3, 2), "USD", 1, Decimal("20"))])
    errors = quality.check(conn, today=date(2026, 3, 2)).errors
    assert any("jen 1 měn" in e for e in errors)
    assert "chybí kurz EUR" in errors


def test_podezrely_skok_a_mezera_jsou_varovani():
    conn = db.connect(":memory:")
    start = date(2026, 1, 5)
    rates = [Rate(start, "EUR", 1, Decimal("24")), Rate(start + timedelta(days=1), "EUR", 1, Decimal("30")),
             Rate(start + timedelta(days=10), "EUR", 1, Decimal("30"))]
    db.upsert(conn, rates)
    report = quality.check(conn, today=start + timedelta(days=10), min_currencies=1)
    assert any("skok 25.0 %" in w for w in report.warnings)
    assert any("mezera" in w for w in report.warnings)
