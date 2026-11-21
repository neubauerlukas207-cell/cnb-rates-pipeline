from datetime import date, timedelta
from decimal import Decimal

import pytest

from cnb_rates.stats import compute


def series(start: date, values: list[float]) -> list[tuple[date, Decimal]]:
    return [(start + timedelta(days=i), Decimal(str(v))) for i, v in enumerate(values)]


def test_zmeny_za_den_a_30_dni():
    values = [100.0] * 30 + [110.0, 121.0]
    s = compute("XYZ", series(date(2026, 3, 1), values))
    assert s.latest == 121.0
    assert s.change_1d_pct == 10.0
    assert s.change_30d_pct == 21.0  # 31 dní zpět je ještě 100


def test_zmena_od_zacatku_roku_proti_konci_predchoziho_roku():
    s = compute("XYZ", series(date(2025, 12, 30), [50.0, 40.0, 44.0]))  # 30. 12., 31. 12., 1. 1.
    assert s.change_ytd_pct == 10.0  # 44 proti 40 (poslední kurz roku 2025)


def test_bez_predchoziho_roku_bere_prvni_letosni_kurz():
    s = compute("XYZ", series(date(2026, 1, 2), [20.0, 21.0, 22.0]))
    assert s.change_ytd_pct == 10.0


def test_minimum_a_maximum_jen_za_posledni_rok():
    old = series(date(2024, 1, 1), [1.0, 999.0])
    recent = series(date(2026, 1, 1), [10.0, 12.0, 11.0])
    s = compute("XYZ", old + recent)
    assert (s.min_1y, s.max_1y) == (10.0, 12.0)


def test_volatilita():
    assert compute("XYZ", series(date(2026, 1, 1), [10.0] * 40)).volatility_30d_pct == 0.0
    noisy = [10.0 + (0.1 if i % 2 else -0.1) for i in range(40)]
    assert compute("XYZ", series(date(2026, 1, 1), noisy)).volatility_30d_pct > 10
    assert compute("XYZ", series(date(2026, 1, 1), [10.0, 11.0])).volatility_30d_pct is None


def test_jeden_zaznam_nema_zmeny():
    s = compute("XYZ", series(date(2026, 1, 1), [10.0]))
    assert (s.change_1d_pct, s.change_30d_pct, s.change_ytd_pct) == (None, None, None)


def test_prazdna_rada_je_chyba():
    with pytest.raises(ValueError):
        compute("XYZ", [])
