"""T032 — Cliente BRAPI: cada status vira a exceção de domínio certa (Artigo VIII)."""

from __future__ import annotations

import httpx
import pytest
import respx

from investimentos.adapters.outbound.brapi.client import BrapiQuoteProvider
from investimentos.domain.exceptions import (
    QuoteNotFoundError,
    QuoteProviderAuthError,
    QuoteProviderContractError,
    QuoteProviderError,
    QuoteProviderRateLimitedError,
    QuoteProviderTimeoutError,
)
from investimentos.domain.model.ticker import Ticker
from tests.conftest import BRAPI_BASE_URL

TICKER = Ticker("PETR4")
QUOTE_URL = f"{BRAPI_BASE_URL}/api/v2/stocks/quote"
PARAMS = {"symbols": "PETR4"}


def rota():
    """Intercepta a chamada do endpoint v2 para PETR4."""
    return respx.get(QUOTE_URL, params=PARAMS)


def _provider(
    client: httpx.AsyncClient, token: str | None = "token-de-teste"
) -> BrapiQuoteProvider:
    return BrapiQuoteProvider(
        client=client, quote_path="/api/v2/stocks/quote?symbols={ticker}", token=token
    )


@pytest.fixture
async def http_client():
    async with httpx.AsyncClient(base_url=BRAPI_BASE_URL, timeout=2.0) as client:
        yield client


@respx.mock
async def test_sucesso_devolve_quote(http_client, brapi_legacy_payload) -> None:
    rota().mock(return_value=httpx.Response(200, json=brapi_legacy_payload))
    quote = await _provider(http_client).fetch(TICKER)
    assert quote.symbol == "PETR4"


@respx.mock
async def test_token_vai_no_header_e_nunca_na_url(http_client, brapi_legacy_payload) -> None:
    """Artigo V — a documentação da BRAPI alerta que token em query vaza para log."""
    route = rota().mock(return_value=httpx.Response(200, json=brapi_legacy_payload))
    await _provider(http_client, token="segredo-super-secreto").fetch(TICKER)

    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer segredo-super-secreto"
    assert "segredo-super-secreto" not in str(request.url)
    assert "token" not in str(request.url).lower()


@respx.mock
async def test_sem_token_nao_envia_authorization(http_client, brapi_legacy_payload) -> None:
    route = rota().mock(return_value=httpx.Response(200, json=brapi_legacy_payload))
    await _provider(http_client, token=None).fetch(TICKER)
    assert "Authorization" not in route.calls.last.request.headers


@respx.mock
@pytest.mark.parametrize(
    ("status", "esperada"),
    [
        (404, QuoteNotFoundError),
        (401, QuoteProviderAuthError),
        (403, QuoteProviderAuthError),
        (429, QuoteProviderRateLimitedError),
        (500, QuoteProviderError),
        (503, QuoteProviderError),
        (418, QuoteProviderError),
    ],
)
async def test_status_da_fonte_vira_excecao_de_dominio(http_client, status, esperada) -> None:
    rota().mock(return_value=httpx.Response(status, json={}))
    with pytest.raises(esperada):
        await _provider(http_client).fetch(TICKER)


@respx.mock
async def test_results_vazio_vira_nao_encontrado(http_client) -> None:
    rota().mock(return_value=httpx.Response(200, json={"results": []}))
    with pytest.raises(QuoteNotFoundError):
        await _provider(http_client).fetch(TICKER)


@respx.mock
async def test_corpo_nao_json_vira_erro_de_contrato(http_client) -> None:
    rota().mock(return_value=httpx.Response(200, text="<html>manutenção</html>"))
    with pytest.raises(QuoteProviderContractError):
        await _provider(http_client).fetch(TICKER)


@respx.mock
async def test_timeout_vira_excecao_de_timeout(http_client) -> None:
    rota().mock(side_effect=httpx.ReadTimeout("demorou"))
    with pytest.raises(QuoteProviderTimeoutError):
        await _provider(http_client).fetch(TICKER)


@respx.mock
async def test_falha_de_rede_vira_erro_da_fonte(http_client) -> None:
    rota().mock(side_effect=httpx.ConnectError("sem rota"))
    with pytest.raises(QuoteProviderError):
        await _provider(http_client).fetch(TICKER)


@respx.mock
async def test_mensagem_de_erro_de_auth_nao_vaza_o_token(http_client) -> None:
    """Artigo V — nem a mensagem de erro pode conter parte da credencial."""
    rota().mock(return_value=httpx.Response(401, json={}))
    with pytest.raises(QuoteProviderAuthError) as exc:
        await _provider(http_client, token="segredo-super-secreto").fetch(TICKER)
    assert "segredo-super-secreto" not in str(exc.value)


@respx.mock
async def test_endpoint_legado_continua_funcionando(http_client, brapi_legacy_payload) -> None:
    """ADR-004 — voltar para a geração antiga é mudar variável de ambiente."""
    respx.get(f"{BRAPI_BASE_URL}/api/quote/PETR4").mock(
        return_value=httpx.Response(200, json=brapi_legacy_payload)
    )
    provider = BrapiQuoteProvider(
        client=http_client,
        quote_path="/api/quote/{ticker}",
        token="token-de-teste",
    )
    quote = await provider.fetch(TICKER)
    assert quote.symbol == "PETR4"


@respx.mock
async def test_payload_real_do_v2_vira_quote(http_client, brapi_v2_payload_real) -> None:
    """O JSON exato do painel da BRAPI atravessa cliente e mapper sem perda."""
    respx.get(QUOTE_URL, params={"symbols": "B3SA3"}).mock(
        return_value=httpx.Response(200, json=brapi_v2_payload_real)
    )
    quote = await _provider(http_client).fetch(Ticker("B3SA3"))

    assert quote.symbol == "B3SA3"
    assert quote.long_name == "B3 SA - Brasil, Bolsa, Balcao"
    assert str(quote.price) == "17.26"
