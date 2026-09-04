"""Fixtures compartilhadas.

Nenhum teste desta suíte (fora de ``tests/contract/``) toca a rede: a BRAPI é
interceptada pelo ``respx`` e o cache é um dublê em memória. Isso atende ao
RNF-06 — a suíte roda offline e no CI.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from investimentos.adapters.inbound.http.app import create_app
from investimentos.config.settings import Settings
from investimentos.domain.model.quote import Quote
from investimentos.domain.model.ticker import Ticker

BRAPI_BASE_URL = "https://brapi.test"


class InMemoryQuoteCache:
    """Dublê de ``QuoteCachePort`` que guarda tudo em um dicionário.

    Existe para tornar o RF-05 verificável sem subir Redis. Respeita o contrato
    de robustez da porta: nunca levanta exceção.
    """

    def __init__(self) -> None:
        self.store: dict[str, Quote] = {}
        self.get_calls = 0
        self.set_calls = 0

    async def get(self, ticker: Ticker) -> Quote | None:
        self.get_calls += 1
        return self.store.get(ticker.value)

    async def set(self, ticker: Ticker, quote: Quote) -> None:
        self.set_calls += 1
        self.store[ticker.value] = quote

    async def ping(self) -> bool:
        return True


class BrokenQuoteCache:
    """Cache que falhou. Devolve miss e engole a gravação, como manda a porta."""

    async def get(self, ticker: Ticker) -> Quote | None:
        return None

    async def set(self, ticker: Ticker, quote: Quote) -> None:
        return None

    async def ping(self) -> bool:
        return False


class StubQuoteProvider:
    """Fonte de cotações controlada pelo teste."""

    def __init__(self, quote: Quote | None = None, error: Exception | None = None) -> None:
        self._quote = quote
        self._error = error
        self.calls = 0

    async def fetch(self, ticker: Ticker) -> Quote:
        self.calls += 1
        if self._error is not None:
            raise self._error
        assert self._quote is not None
        return self._quote


@pytest.fixture
def sample_quote() -> Quote:
    return Quote(
        ticker=Ticker("PETR4"),
        short_name="PETR4",
        long_name="Petroleo Brasileiro SA Petrobras",
        currency="BRL",
        price=Decimal("36.65"),
        change=Decimal("-0.35"),
        change_percent=Decimal("-0.95"),
        volume=27681100,
        market_cap=Decimal("483937892568"),
        quoted_at=datetime(2026, 9, 3, 17, 24, 54, tzinfo=timezone.utc),
    )


@pytest.fixture
def brapi_legacy_payload() -> dict[str, Any]:
    """Formato legado: campos na raiz do item (ADR-004)."""
    return {
        "results": [
            {
                "symbol": "PETR4",
                "shortName": "PETR4",
                "longName": "Petroleo Brasileiro SA Petrobras",
                "currency": "BRL",
                "regularMarketPrice": 36.65,
                "regularMarketChange": -0.35,
                "regularMarketChangePercent": -0.95,
                "regularMarketVolume": 27681100,
                "regularMarketTime": "2026-09-03T17:24:54.000Z",
                "marketCap": 483937892568,
            }
        ],
        "requestedAt": "2026-09-03T17:25:28.170Z",
    }


@pytest.fixture
def brapi_v2_payload(brapi_legacy_payload: dict[str, Any]) -> dict[str, Any]:
    """Formato v2, na forma real: 'symbol' fora, dados de mercado sob 'data'."""
    item = dict(brapi_legacy_payload["results"][0])
    symbol = item.pop("symbol")
    return {
        "results": [
            {
                "requestedSymbol": symbol,
                "symbol": symbol,
                "changed": False,
                "data": item,
            }
        ],
        "requestedAt": brapi_legacy_payload["requestedAt"],
    }


@pytest.fixture
def brapi_v2_payload_real() -> dict[str, Any]:
    """Payload copiado literalmente do painel da BRAPI em 2026-09-03.

    Serve de regressão: se a nossa leitura do contrato quebrar, este teste
    falha mesmo sem rede e sem token.
    """
    return {
        "results": [
            {
                "requestedSymbol": "B3SA3",
                "symbol": "B3SA3",
                "changed": False,
                "data": {
                    "shortName": "B3SA3",
                    "longName": "B3 SA - Brasil, Bolsa, Balcao",
                    "currency": "BRL",
                    "regularMarketPrice": 17.26,
                    "regularMarketDayHigh": 17.57,
                    "regularMarketDayLow": 16.71,
                    "regularMarketDayRange": "16.71 - 17.57",
                    "regularMarketChange": 0.64,
                    "regularMarketChangePercent": 3.85,
                    "regularMarketTime": "2026-09-03T03:54:59.000Z",
                    "marketCap": 80748160464,
                    "regularMarketVolume": 41077700,
                    "regularMarketPreviousClose": 17.33,
                    "regularMarketOpen": 16.74,
                    "fiftyTwoWeekRange": "12.16 - 20.33",
                    "fiftyTwoWeekLow": 12.16,
                    "fiftyTwoWeekHigh": 20.33,
                    "logourl": "https://icons.brapi.dev/icons/B3SA3.svg",
                },
            }
        ],
        "requestedAt": "2026-09-03T12:12:29.182Z",
        "took": 1,
    }


@pytest.fixture
def test_settings() -> Settings:
    """Configuração isolada: ignora o .env da máquina e desliga o Redis."""
    return Settings(
        _env_file=None,
        app_env="test",
        log_level="WARNING",
        brapi_base_url=BRAPI_BASE_URL,
        brapi_quote_path="/api/v2/stocks/quote?symbols={ticker}",
        brapi_token="token-de-teste",
        redis_url=None,
    )


@pytest.fixture
def client(test_settings: Settings):
    """Cliente HTTP da aplicação, com o ciclo de vida executado."""
    app = create_app(test_settings)
    with TestClient(app) as test_client:
        yield test_client
