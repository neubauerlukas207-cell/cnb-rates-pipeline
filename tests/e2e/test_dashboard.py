"""Dashboard v prohlížeči (Playwright). Spuštění: pytest -m e2e"""

import functools
import http.server
import threading
from datetime import date

import pytest

from cnb_rates.cli import main

playwright = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def site_url(tmp_path_factory, request):
    """Sestaví web z uložených dat ČNB a spustí ho na lokálním HTTP serveru."""
    tmp = tmp_path_factory.mktemp("site")
    client = request.getfixturevalue("fake_cnb_module")
    assert main(["--db", str(tmp / "rates.db"), "run", "--out", str(tmp / "public"), "--years", "2026"],
                client=client, today=date(2026, 11, 21)) == 0
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp / "public"))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/"
    server.shutdown()


@pytest.fixture(scope="module")
def fake_cnb_module():
    import httpx

    from cnb_rates.fetch import BASE_URL, CnbClient
    from tests.conftest import fixture

    def handler(req):
        name = "rok_2026_zacatek.txt" if req.url.path.endswith("rok.txt") else "denni_2026-11-20.txt"
        return httpx.Response(200, text=fixture(name))

    return CnbClient(httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler)), backoff=0)


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture(params=[(1280, 800), (390, 844)], ids=["desktop", "mobil"])
def page(browser, site_url, request):
    width, height = request.param
    page = browser.new_page(viewport={"width": width, "height": height})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.goto(site_url)
    page.wait_for_selector("#table tbody tr")
    yield page
    assert errors == [], f"chyby v konzoli: {errors}"
    page.close()


def test_nacte_data_karty_a_tabulku(page):
    assert "20. 11. 2026" in page.inner_text("#meta")
    assert page.locator(".card").count() == 4
    assert page.locator("#table tbody tr").count() == 30
    assert "24,470 Kč" in page.inner_text(".card[data-code='EUR']")


def test_graf_se_prepne_na_jinou_menu_a_obdobi(page):
    assert page.inner_text("#chart-title") == "Vývoj kurzu EUR"
    page.select_option("#currency", "USD")
    assert page.inner_text("#chart-title") == "Vývoj kurzu USD"
    page.click(".range button[data-days='30']")
    assert page.get_attribute("#chart", "data-points") == "30"
    page.click(".range button[data-days='365']")
    assert int(page.get_attribute("#chart", "data-points")) == 41  # tolik dní je ve vzorku dat
    assert page.locator("#chart path.line").count() == 1


def test_klik_na_kartu_prepne_graf(page):
    page.click(".card[data-code='GBP']")
    assert page.inner_text("#chart-title") == "Vývoj kurzu GBP"


def test_razeni_tabulky(page):
    page.click("#table th[data-key='latest']")
    first = page.inner_text("#table tbody tr:first-child th")
    page.click("#table th[data-key='latest']")
    last_sorted_first = page.inner_text("#table tbody tr:first-child th")
    assert first == "IDR"  # nejlevnější měna za jednotku
    assert last_sorted_first != first
    assert page.get_attribute("#table th[data-key='latest']", "aria-sort") == "descending"


def test_prevodnik(page):
    page.fill("#conv-amount", "100")
    page.select_option("#conv-currency", "EUR")
    assert page.inner_text("#conv-result").replace(" ", " ") == "100,00 EUR = 2 447,00 Kč"
    page.fill("#conv-amount", "-5")
    assert page.inner_text("#conv-result") == "–"


def test_bez_vodorovneho_posuvniku(page):
    overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    assert overflow <= 0
