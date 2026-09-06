"""T047 — Contract test: bate na BRAPI de verdade.

Opt-in por decisão da clarificação Q6 da Spec 001:

    pytest -m contract

Fora do CI porque consome cota do token e depende de rede. É, no entanto, a
única prova de que o nosso mapper corresponde ao que a BRAPI devolve hoje.

Na Spec 002 ele ganhou duas responsabilidades novas, registradas como itens em
aberto no checklist de requisitos:

- **CHK024** — qual o teto real de ativos por chamada no plano gratuito. A
  documentação publica 10 no Startup e 20 no Pro, mas não o do gratuito.
- **CHK025** — o que a fonte faz quando um código do lote não existe. A spec
  assume que ela omite o ausente de `results`; se em vez disso o lote inteiro
  falhar, o FR-011 precisa mudar.

Se este teste falhar, quem está errado é
``specs/002-multiplos-tickers/contracts/brapi-quote.md`` — não a BRAPI.
"""

from __future__ import annotations

import os

import httpx
import pytest

from investimentos.adapters.outbound.brapi.client import BrapiQuoteProvider
from investimentos.adapters.outbound.brapi.mapper import extract_items, to_quotes
from investimentos.domain.model.ticker import Ticker

pytestmark = pytest.mark.contract

BASE_URL = os.getenv("BRAPI_BASE_URL", "https://brapi.dev")
QUOTE_PATH = os.getenv("BRAPI_QUOTE_PATH", "/api/v2/stocks/quote?symbols={ticker}")
TOKEN = os.getenv("BRAPI_TOKEN")

# Tickers de sandbox: respondem mesmo sem token.
PETR4, VALE3, ITUB4 = Ticker("PETR4"), Ticker("VALE3"), Ticker("ITUB4")
INEXISTENTE = Ticker("ZZZZ9")


@pytest.fixture
async def provider():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        yield BrapiQuoteProvider(client=client, quote_path=QUOTE_PATH, token=TOKEN)


async def _get(codigos: str) -> httpx.Response:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        headers = {"Accept": "application/json"}
        if TOKEN:
            headers["Authorization"] = f"Bearer {TOKEN}"
        return await client.get(QUOTE_PATH.format(ticker=codigos), headers=headers)


async def test_um_ativo_responde_200() -> None:
    resposta = await _get("PETR4")
    assert resposta.status_code == 200


async def test_item_traz_os_campos_obrigatorios() -> None:
    """Os dois campos sem os quais não existe cotação."""
    itens = extract_items((await _get("PETR4")).json())
    assert itens, "a fonte devolveu results vazio para um ticker de sandbox"
    assert "symbol" in itens[0], f"campos recebidos: {sorted(itens[0])}"
    assert "regularMarketPrice" in itens[0], f"campos recebidos: {sorted(itens[0])}"


async def test_varios_ativos_numa_chamada_so() -> None:
    """ADR-009 — a premissa em que toda a economia de cota se apoia."""
    resposta = await _get("PETR4,VALE3,ITUB4")
    assert resposta.status_code == 200

    quotes = to_quotes(resposta.json(), [PETR4, VALE3, ITUB4])
    assert set(quotes) == {PETR4, VALE3, ITUB4}, (
        f"a fonte devolveu {sorted(t.value for t in quotes)} — "
        "se vier menos que os três, o lote não está sendo atendido numa chamada"
    )


async def test_mapper_produz_quotes_validas_do_payload_real() -> None:
    quotes = to_quotes((await _get("PETR4,VALE3")).json(), [PETR4, VALE3])
    for ticker, quote in quotes.items():
        assert quote.symbol == ticker.value
        assert quote.price > 0
        assert quote.quoted_at.tzinfo is not None


async def test_teto_de_ativos_por_chamada_do_plano(provider) -> None:
    """CHK024 — descobre, sem adivinhar, quantos ativos o plano aceita.

    Não falha se o teto for menor que o pedido: apenas registra quantos vieram,
    para que o número entre na spec como fato e não como aposta.
    """
    pedidos = [PETR4, VALE3, ITUB4]
    quotes = await provider.fetch_many(pedidos)

    print(f"\n[CHK024] pedidos={len(pedidos)} atendidos={len(quotes)}")
    assert quotes, "nenhum ativo veio — o plano pode não aceitar consulta múltipla"


async def test_codigo_inexistente_no_lote_nao_derruba_os_outros(provider) -> None:
    """CHK025 — a premissa do FR-011 confrontada com a realidade."""
    quotes = await provider.fetch_many([PETR4, INEXISTENTE])

    assert PETR4 in quotes, (
        "a fonte não atendeu PETR4 quando ZZZZ9 estava no mesmo lote — "
        "o FR-011 precisa ser revisto"
    )
    assert INEXISTENTE not in quotes
