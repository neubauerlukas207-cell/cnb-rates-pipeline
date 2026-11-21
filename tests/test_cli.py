import json
from datetime import date

from cnb_rates.cli import main


def test_cela_pipeline_od_stazeni_po_web(tmp_path, fake_cnb):
    out = tmp_path / "public"
    code = main(["--db", str(tmp_path / "rates.db"), "run", "--out", str(out), "--years", "2026"],
                client=fake_cnb, today=date(2026, 11, 21))
    assert code == 0
    assert {p.name for p in out.iterdir()} == {"index.html", "app.js", "style.css", "data.json"}

    data = json.loads((out / "data.json").read_text(encoding="utf-8"))
    assert data["latest_day"] == "2026-11-20"
    codes = [c["code"] for c in data["currencies"]]
    assert codes[:6] == ["EUR", "USD", "GBP", "CHF", "PLN", "JPY"]  # hlavní měny první
    eur = data["currencies"][0]
    assert eur["latest"] == 24.47
    assert eur["history"][-1] == ["2026-11-20", 24.47]
    assert eur["history"][0][0] == "2026-01-02"
    jpy = next(c for c in data["currencies"] if c["code"] == "JPY")
    assert jpy["latest"] == 0.14031  # 100 JPY = 14,031 Kč


def test_spatna_data_web_nepublikuji(tmp_path, fake_cnb):
    out = tmp_path / "public"
    # „dnes“ daleko v budoucnu → data jsou zastaralá → kontrola kvality selže
    code = main(["--db", str(tmp_path / "rates.db"), "run", "--out", str(out), "--years", "2026"],
                client=fake_cnb, today=date(2027, 6, 1))
    assert code == 1
    assert not out.exists()


def test_opakovane_spusteni_je_idempotentni(tmp_path, fake_cnb):
    args = ["--db", str(tmp_path / "rates.db"), "update", "--years", "2026"]
    assert main(args, client=fake_cnb, today=date(2026, 11, 21)) == 0
    assert main(args, client=fake_cnb, today=date(2026, 11, 21)) == 0
    import sqlite3

    count = sqlite3.connect(tmp_path / "rates.db").execute("SELECT COUNT(*) FROM rates").fetchone()[0]
    assert count == 40 * 30 + 30  # roční vzorek + denní lístek z jiného dne
