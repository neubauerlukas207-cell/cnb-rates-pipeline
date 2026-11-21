from pathlib import Path

import httpx
import pytest

from cnb_rates.fetch import BASE_URL, CnbClient

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture
def daily_text() -> str:
    return fixture("denni_2026-11-20.txt")


@pytest.fixture
def yearly_text() -> str:
    return fixture("rok_2026_zacatek.txt")


@pytest.fixture
def fake_cnb() -> CnbClient:
    """Klient, který místo sítě vrací uložené soubory ČNB."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("rok.txt"):
            return httpx.Response(200, text=fixture("rok_2026_zacatek.txt"))
        if request.url.path.endswith("denni_kurz.txt"):
            return httpx.Response(200, text=fixture("denni_2026-11-20.txt"))
        return httpx.Response(404)

    return CnbClient(httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler)), backoff=0)
