from datetime import date
from decimal import Decimal

from cnb_rates import db
from cnb_rates.parse import Rate, parse_yearly
from tests.conftest import fixture


def test_opakovany_zapis_nic_nezdvoji(yearly_text):
    conn = db.connect(":memory:")
    rates = parse_yearly(yearly_text)
    db.upsert(conn, rates)
    db.upsert(conn, rates)
    assert conn.execute("SELECT COUNT(*) FROM rates").fetchone()[0] == len(rates)


def test_oprava_kurzu_prepise_puvodni_hodnotu():
    conn = db.connect(":memory:")
    day = date(2026, 11, 20)
    db.upsert(conn, [Rate(day, "EUR", 1, Decimal("24.470"))])
    db.upsert(conn, [Rate(day, "EUR", 1, Decimal("24.480"))])
    assert db.history(conn, "EUR") == [(day, Decimal("24.480"))]


def test_kurz_je_ulozen_presne_bez_zaokrouhleni_floatu():
    conn = db.connect(":memory:")
    db.upsert(conn, [Rate(date(2026, 1, 2), "IDR", 1000, Decimal("1.233"))])
    assert conn.execute("SELECT rate FROM rates").fetchone()[0] == "1.233"
    assert db.history(conn, "IDR")[0][1] == Decimal("0.001233")


def test_aktualni_meny_bez_vyrazenych():
    conn = db.connect(":memory:")
    db.upsert(conn, parse_yearly(fixture("rok_2022_zmena_hlavicky.txt")))
    codes = db.currencies(conn)
    assert "EUR" in codes
    assert "RUB" not in codes  # po 1. 3. 2022 se nevyhlašuje
    assert db.history(conn, "RUB")  # historie ale zůstává


def test_soubor_se_vytvori_i_se_slozkou(tmp_path):
    path = tmp_path / "nova" / "slozka" / "rates.db"
    conn = db.connect(path)
    db.upsert(conn, [Rate(date(2026, 1, 2), "EUR", 1, Decimal("24.17"))])
    conn.close()
    assert db.days(db.connect(path)) == [date(2026, 1, 2)]
