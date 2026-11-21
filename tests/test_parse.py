from datetime import date
from decimal import Decimal

import pytest

from cnb_rates.parse import ParseError, parse_daily, parse_yearly
from tests.conftest import fixture


def test_denni_listek_ze_skutecnych_dat(daily_text):
    day, rates = parse_daily(daily_text)
    assert day == date(2026, 11, 20)
    by_code = {r.code: r for r in rates}
    assert len(rates) == 30
    assert by_code["EUR"].rate == Decimal("24.470")
    assert by_code["EUR"].amount == 1


def test_mnozstvi_se_prepocita_na_jednu_jednotku(daily_text):
    _, rates = parse_daily(daily_text)
    php = next(r for r in rates if r.code == "PHP")
    assert php.amount == 100
    assert php.per_unit == Decimal("0.34907")


def test_rocni_historie(yearly_text):
    rates = parse_yearly(yearly_text)
    days = sorted({r.day for r in rates})
    assert days[0] == date(2026, 1, 2)
    assert len(days) == 40
    assert len(rates) == 40 * 30  # 30 měn v hlavičce
    jpy = next(r for r in rates if r.code == "JPY" and r.day == date(2026, 1, 2))
    assert (jpy.amount, jpy.rate) == (100, Decimal("13.141"))


def test_zmena_hlavicky_v_roce_2022_rubl_zmizel():
    rates = parse_yearly(fixture("rok_2022_zmena_hlavicky.txt"))
    rub_days = {r.day for r in rates if r.code == "RUB"}
    assert date(2022, 3, 1) in rub_days
    assert all(d < date(2022, 3, 2) for d in rub_days)
    assert any(r.code == "EUR" and r.day == date(2022, 3, 4) for r in rates)


@pytest.mark.parametrize(
    "text, message",
    [
        ("", "prázdný"),
        ("20.11.2026 #223\nšpatná hlavička\nEMU|euro|1|EUR|24,470", "hlavička"),
        ("20.11.2026 #223\nzemě|měna|množství|kód|kurz\nEMU|euro|1|EUR", "5 sloupců"),
        ("20.11.2026 #223\nzemě|měna|množství|kód|kurz\nEMU|euro|1|EUR|abc", "neplatné číslo"),
        ("20.11.2026 #223\nzemě|měna|množství|kód|kurz\nEMU|euro|1|EUR|-1,5", "kladný"),
        ("20.11.2026 #223\nzemě|měna|množství|kód|kurz\nEMU|euro|1|eur|24,470", "kód měny"),
        ("32.13.2026 #1\nzemě|měna|množství|kód|kurz\nEMU|euro|1|EUR|24,470", "datum"),
    ],
)
def test_vadny_denni_listek_vyhodi_srozumitelnou_chybu(text, message):
    with pytest.raises(ParseError, match=message):
        parse_daily(text)


def test_vadna_rocni_historie():
    with pytest.raises(ParseError, match="před hlavičkou"):
        parse_yearly("02.01.2026|13,797")
    with pytest.raises(ParseError, match="sloupců"):
        parse_yearly("Datum|1 AUD|1 EUR\n02.01.2026|13,797")
    with pytest.raises(ParseError, match="hlavička"):
        parse_yearly("Datum|AUD\n02.01.2026|13,797")


def test_prazdna_bunka_znamena_nevyhlaseny_kurz():
    rates = parse_yearly("Datum|1 AUD|1 EUR\n02.01.2026||24,170\n")
    assert [(r.code, r.rate) for r in rates] == [("EUR", Decimal("24.170"))]
