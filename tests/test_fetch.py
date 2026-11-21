from datetime import date

import httpx
import pytest

from cnb_rates.fetch import BASE_URL, CnbClient
from tests.conftest import fixture


def client(handler) -> CnbClient:
    return CnbClient(httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler)), retries=3, backoff=0)


def test_posle_datum_ve_formatu_cnb():
    seen = []

    def handler(request):
        seen.append(request.url.params.get("date"))
        return httpx.Response(200, text=fixture("denni_2026-11-20.txt"))

    day, rates = client(handler).daily(date(2026, 11, 20))
    assert seen == ["20.11.2026"]
    assert day == date(2026, 11, 20) and len(rates) == 30


def test_pri_vypadku_serveru_to_zkusi_znovu():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(503) if len(calls) < 3 else httpx.Response(200, text=fixture("rok_2026_zacatek.txt"))

    assert client(handler).year(2026)
    assert len(calls) == 3


def test_po_vycerpani_pokusu_selze():
    def handler(request):
        raise httpx.ConnectError("síť nedostupná")

    with pytest.raises(RuntimeError, match="3 pokusech"):
        client(handler).year(2026)


def test_chyba_404_se_neopakuje():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(404)

    with pytest.raises(httpx.HTTPStatusError):
        client(handler).year(1990)
    assert len(calls) == 1
