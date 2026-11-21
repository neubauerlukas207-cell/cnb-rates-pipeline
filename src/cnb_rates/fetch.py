"""HTTP klient na veřejné textové rozhraní ČNB (bez klíče)."""

from __future__ import annotations

import logging
import time
from datetime import date

import httpx

from .parse import Rate, parse_daily, parse_yearly

log = logging.getLogger(__name__)

BASE_URL = "https://www.cnb.cz/cs/financni-trhy/devizovy-trh/kurzy-devizoveho-trhu/kurzy-devizoveho-trhu/"


class CnbClient:
    def __init__(self, http: httpx.Client | None = None, retries: int = 3, backoff: float = 1.0):
        self.http = http or httpx.Client(base_url=BASE_URL, timeout=20, headers={"User-Agent": "cnb-rates-pipeline"})
        self.retries = retries
        self.backoff = backoff

    def _get(self, path: str, params: dict[str, str]) -> str:
        """GET s opakováním při výpadku sítě nebo chybě 5xx (exponenciální čekání)."""
        for attempt in range(1, self.retries + 1):
            try:
                response = self.http.get(path, params=params)
                if response.status_code < 500:
                    response.raise_for_status()
                    return response.text
                log.warning("ČNB vrátila %s (pokus %s/%s)", response.status_code, attempt, self.retries)
            except httpx.TransportError as e:
                log.warning("Chyba spojení s ČNB: %s (pokus %s/%s)", e, attempt, self.retries)
            if attempt < self.retries:
                time.sleep(self.backoff * 2 ** (attempt - 1))
        raise RuntimeError(f"ČNB neodpovídá ani po {self.retries} pokusech: {path}")

    def daily(self, day: date | None = None) -> tuple[date, list[Rate]]:
        params = {"date": day.strftime("%d.%m.%Y")} if day else {}
        return parse_daily(self._get("denni_kurz.txt", params))

    def year(self, year: int) -> list[Rate]:
        return parse_yearly(self._get("rok.txt", {"rok": str(year)}))
