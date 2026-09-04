"""T070 — Contract test: bate na BRAPI de verdade.

Opt-in por decisão da clarificação Q6:

    pytest -m contract

Fora do CI porque consome cota do token e depende de rede. É, no entanto, a
**única** prova de que o nosso mapper corresponde ao que a BRAPI devolve hoje —
especialmente relevante porque a documentação pública apresenta duas gerações de
resposta (ADR-004) e não foi possível confirmar qual está ativa.

Se este teste falhar, quem está errado é
``specs/001-cotacao-ticker/contracts/brapi-quote.md``, não a BRAPI.
"""

from __future__ import annotations

import os

import httpx
import pytest

from investimentos.adapters.outbound.brapi.client import BrapiQuoteProvider
from investimentos.adapters.outbound.brapi.mapper import extract_first_item, to_quote
from investimentos.domain.exceptions import QuoteNotFoundError
from investimentos.domain.model.ticker import Ticker

pytestmark = pytest.mark.contract

BASE_URL = os.getenv("BRAPI_BASE_URL", "https://brapi.dev")
QUOTE_PATH = os.getenv("BRAPI_QUOTE_PATH", "/api/v2/stocks/quote?symbols={ticker}")
TOKEN = os.getenv("BRAPI_TOKEN")

# Tickers de sandbox: respondem mesmo sem token.
TICKER = Ticker("PETR4")
TICKER_INEXISTENTE = Ticker("ZZZZ9")


@pytest.fixture
async def provider():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        yield BrapiQuoteProvider(client=client, quote_path=QUOTE_PATH, token=TOKEN)


@pytest.fixture
async def payload_real():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        headers = {"Accept": "application/json"}
        if TOKEN:
            headers["Authorization"] = f"Bearer {TOKEN}"
        resposta = await client.get(QUOTE_PATH.format(ticker=TICKER.value), headers=headers)
        resposta.raise_for_status()
        return resposta.json()


async def test_endpoint_responde_200(payload_real) -> None:
    assert isinstance(payload_real, dict)


async def test_payload_traz_results_como_lista_nao_vazia(payload_real) -> None:
    assert isinstance(payload_real.get("results"), list)
    assert payload_real["results"], "a fonte devolveu results vazio para um ticker de sandbox"


async def test_item_traz_os_campos_obrigatorios(payload_real) -> None:
    """Os dois campos sem os quais não existe cotação."""
    item = extract_first_item(payload_real)
    assert item is not None
    assert "symbol" in item, f"campos recebidos: {sorted(item)}"
    assert "regularMarketPrice" in item, f"campos recebidos: {sorted(item)}"


async def test_mapper_produz_quote_valido_a_partir_do_payload_real(payload_real) -> None:
    """A prova final: o nosso mapper entende a resposta que a BRAPI dá hoje."""
    item = extract_first_item(payload_real)
    assert item is not None
    quote = to_quote(item, TICKER)

    assert quote.symbol == "PETR4"
    assert quote.price > 0
    assert quote.currency == "BRL"
    assert quote.quoted_at.tzinfo is not None


async def test_fluxo_completo_do_provider(provider) -> None:
    quote = await provider.fetch(TICKER)
    assert quote.symbol == "PETR4"
    assert quote.price > 0


async def test_ticker_inexistente_vira_nao_encontrado(provider) -> None:
    with pytest.raises(QuoteNotFoundError):
        await provider.fetch(TICKER_INEXISTENTE)
