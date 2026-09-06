"""T022, T023 — A resposta diz por quanto tempo ainda vale (US3)."""

from __future__ import annotations

import httpx
import respx
from fastapi.testclient import TestClient

from investimentos.adapters.inbound.http.app import create_app
from investimentos.adapters.inbound.http.dependencies import get_quotes_use_case
from investimentos.adapters.outbound.brapi.client import BrapiQuoteProvider
from investimentos.application.usecases.get_quote import GetQuotesUseCase
from investimentos.domain.model.ticker import Ticker
from tests.conftest import QUOTE_URL, InMemoryQuoteCache, build_quote


def _rota(*codigos: str):
    return respx.get(QUOTE_URL, params={"symbols": ",".join(codigos)})


def _app_com_cache(test_settings, cache: InMemoryQuoteCache, ttl: int = 60):
    app = create_app(test_settings)
    return app, cache, ttl


@respx.mock
def test_cotacao_da_fonte_anuncia_o_ttl_cheio(test_settings, payload_v2) -> None:
    """Acabou de ser gravada: vale tudo."""
    _rota("ITSA4").mock(return_value=httpx.Response(200, json=payload_v2("ITSA4")))
    app = create_app(test_settings)

    with TestClient(app) as c:
        provider = BrapiQuoteProvider(
            client=app.state.container._http_client,
            quote_path=test_settings.brapi_quote_path,
            token=test_settings.brapi_token_value,
        )
        app.dependency_overrides[get_quotes_use_case] = lambda: GetQuotesUseCase(
            provider, InMemoryQuoteCache(), max_tickers=3, cache_ttl_seconds=60
        )
        resposta = c.get("/acoes/ITSA4")

    assert resposta.headers["Cache-Control"] == "public, max-age=60"


@respx.mock
def test_cotacao_do_cache_anuncia_a_validade_restante(test_settings, payload_v2) -> None:
    """FR-009, SC-004 — anunciar o TTL cheio aqui seria mentir por 45 segundos."""
    _rota("ITSA4").mock(return_value=httpx.Response(200, json=payload_v2("ITSA4")))
    app = create_app(test_settings)
    cache = InMemoryQuoteCache(ttl_seconds=15)

    with TestClient(app) as c:
        import asyncio

        asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            cache.set_many([build_quote("ITSA4")])
        )
        provider = BrapiQuoteProvider(
            client=app.state.container._http_client,
            quote_path=test_settings.brapi_quote_path,
            token=test_settings.brapi_token_value,
        )
        app.dependency_overrides[get_quotes_use_case] = lambda: GetQuotesUseCase(
            provider, cache, max_tickers=3, cache_ttl_seconds=60
        )
        resposta = c.get("/acoes/ITSA4")

    assert resposta.headers["Cache-Control"] == "public, max-age=15"


@respx.mock
def test_lista_usa_a_menor_validade(test_settings, payload_v2) -> None:
    """FR-010, ADR-019 — a lista deixa de servir quando o primeiro item vence."""
    _rota("PETR4").mock(return_value=httpx.Response(200, json=payload_v2("PETR4")))
    app = create_app(test_settings)
    cache = InMemoryQuoteCache()
    cache.ttl_por_ticker[Ticker("ITSA4")] = 12

    with TestClient(app) as c:
        import asyncio

        asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            cache.set_many([build_quote("ITSA4")])
        )
        provider = BrapiQuoteProvider(
            client=app.state.container._http_client,
            quote_path=test_settings.brapi_quote_path,
            token=test_settings.brapi_token_value,
        )
        app.dependency_overrides[get_quotes_use_case] = lambda: GetQuotesUseCase(
            provider, cache, max_tickers=3, cache_ttl_seconds=60
        )
        resposta = c.get("/acoes?ticker=ITSA4&ticker=PETR4")

    # ITSA4 vale 12 e PETR4 acabou de ser buscado (60). Vence o menor.
    assert resposta.headers["Cache-Control"] == "public, max-age=12"


@respx.mock
def test_sem_cache_configurado_e_no_store(client, payload_v2) -> None:
    """FR-012 — sem cache não há validade a prometer."""
    _rota("ITSA4").mock(return_value=httpx.Response(200, json=payload_v2("ITSA4")))

    resposta = client.get("/acoes/ITSA4")

    assert resposta.headers["Cache-Control"] == "no-store"


@respx.mock
def test_lista_sem_nenhuma_cotacao_e_no_store(client, payload_v2) -> None:
    _rota("ZZZZ9").mock(return_value=httpx.Response(200, json={"results": []}))

    resposta = client.get("/acoes?ticker=ZZZZ9")

    assert resposta.status_code == 200
    assert resposta.headers["Cache-Control"] == "no-store"


def test_erro_de_validacao_nao_e_cacheavel(client) -> None:
    """FR-011."""
    assert client.get("/acoes/PETR").headers["Cache-Control"] == "no-store"


@respx.mock
def test_erro_da_fonte_nao_e_cacheavel(client) -> None:
    _rota("ITSA4").mock(return_value=httpx.Response(500, json={}))
    assert client.get("/acoes/ITSA4").headers["Cache-Control"] == "no-store"


def test_erro_de_limite_nao_e_cacheavel(client) -> None:
    resposta = client.get("/acoes?ticker=A1A1&ticker=B2B2&ticker=C3C3&ticker=D4D4")
    assert resposta.status_code == 400
    assert resposta.headers["Cache-Control"] == "no-store"
