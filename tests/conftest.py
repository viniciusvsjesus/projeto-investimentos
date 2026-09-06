"""Fixtures compartilhadas.

Nenhum teste desta suíte (fora de ``tests/contract/``) toca a rede: a BRAPI é
interceptada pelo ``respx`` e o cache é um dublê em memória. Isso atende ao
SC-007 — a suíte roda offline e no CI.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
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
QUOTE_PATH = "/api/v2/stocks/quote?symbols={ticker}"
QUOTE_URL = f"{BRAPI_BASE_URL}/api/v2/stocks/quote"


class InMemoryQuoteCache:
    """Dublê de ``QuoteCachePort`` que guarda tudo em um dicionário.

    Existe para tornar a economia de cota verificável sem subir Redis. Respeita
    o contrato de robustez da porta: nunca levanta exceção.
    """

    def __init__(self) -> None:
        self.store: dict[Ticker, Quote] = {}
        self.get_calls: list[tuple[Ticker, ...]] = []
        self.set_calls: list[tuple[Ticker, ...]] = []

    async def get_many(self, tickers: Sequence[Ticker]) -> Mapping[Ticker, Quote]:
        self.get_calls.append(tuple(tickers))
        return {t: self.store[t] for t in tickers if t in self.store}

    async def set_many(self, quotes: Iterable[Quote]) -> None:
        lista = list(quotes)
        self.set_calls.append(tuple(q.ticker for q in lista))
        for q in lista:
            self.store[q.ticker] = q

    async def ping(self) -> bool:
        return True


class BrokenQuoteCache:
    """Cache que falhou. Devolve vazio e engole a gravação, como manda a porta."""

    async def get_many(self, tickers: Sequence[Ticker]) -> Mapping[Ticker, Quote]:
        return {}

    async def set_many(self, quotes: Iterable[Quote]) -> None:
        return None

    async def ping(self) -> bool:
        return False


class StubQuoteProvider:
    """Fonte de cotações controlada pelo teste.

    Guarda cada chamada para que o teste possa afirmar **quantas** vezes a fonte
    foi consultada e **com quais** ativos — que é o que os SC-001 a SC-004 pedem.
    """

    def __init__(
        self,
        quotes: Iterable[Quote] = (),
        error: Exception | None = None,
    ) -> None:
        self._quotes = {q.ticker: q for q in quotes}
        self._error = error
        self.calls: list[tuple[Ticker, ...]] = []

    @property
    def call_count(self) -> int:
        return len(self.calls)

    async def fetch_many(self, tickers: Sequence[Ticker]) -> Mapping[Ticker, Quote]:
        self.calls.append(tuple(tickers))
        if self._error is not None:
            raise self._error
        return {t: self._quotes[t] for t in tickers if t in self._quotes}


def build_quote(
    codigo: str = "PETR4",
    price: str = "36.65",
    short_name: str | None = None,
    long_name: str | None = "Petroleo Brasileiro SA Petrobras",
) -> Quote:
    return Quote(
        ticker=Ticker(codigo),
        short_name=short_name or codigo,
        long_name=long_name,
        currency="BRL",
        price=Decimal(price),
        change=Decimal("-0.35"),
        change_percent=Decimal("-0.95"),
        volume=27681100,
        market_cap=Decimal("483937892568"),
        quoted_at=datetime(2026, 9, 6, 17, 24, 54, tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_quote() -> Quote:
    return build_quote()


def _item_v2(codigo: str, price: float = 36.65, long_name: str | None = None) -> dict[str, Any]:
    """Um item no formato real do v2: symbol fora, dados de mercado sob 'data'."""
    return {
        "requestedSymbol": codigo,
        "symbol": codigo,
        "changed": False,
        "data": {
            "shortName": codigo,
            "longName": long_name or f"{codigo} SA",
            "currency": "BRL",
            "regularMarketPrice": price,
            "regularMarketChange": -0.35,
            "regularMarketChangePercent": -0.95,
            "regularMarketVolume": 27681100,
            "regularMarketTime": "2026-09-06T17:24:54.000Z",
            "marketCap": 483937892568,
        },
    }


@pytest.fixture
def payload_v2():
    """Fábrica de payloads do v2 com quantos ativos o teste quiser."""

    def _build(*codigos: str) -> dict[str, Any]:
        return {
            "results": [_item_v2(c) for c in codigos],
            "requestedAt": "2026-09-06T12:12:29.182Z",
            "took": 1,
        }

    return _build


@pytest.fixture
def brapi_legacy_payload() -> dict[str, Any]:
    """Formato legado: todos os campos na raiz do item (ADR-004)."""
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
                "regularMarketTime": "2026-09-06T17:24:54.000Z",
                "marketCap": 483937892568,
            }
        ],
        "requestedAt": "2026-09-06T12:12:29.182Z",
    }


@pytest.fixture
def brapi_v2_payload(payload_v2) -> dict[str, Any]:
    return payload_v2("PETR4")


@pytest.fixture
def brapi_v2_payload_real() -> dict[str, Any]:
    """Payload copiado literalmente do painel da BRAPI em 2026-09-03.

    Regressão: se a nossa leitura do contrato quebrar, este teste falha mesmo
    sem rede e sem token.
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
        brapi_quote_path=QUOTE_PATH,
        brapi_token="token-de-teste",
        redis_url=None,
        max_tickers_per_request=3,
    )


@pytest.fixture
def client(test_settings: Settings):
    """Cliente HTTP da aplicação, com o ciclo de vida executado."""
    app = create_app(test_settings)
    with TestClient(app) as test_client:
        yield test_client
