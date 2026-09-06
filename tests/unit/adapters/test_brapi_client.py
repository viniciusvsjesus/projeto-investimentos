"""T010, T039 — Cliente BRAPI."""

from __future__ import annotations

import httpx
import pytest
import respx

from investimentos.adapters.outbound.brapi.client import BrapiQuoteProvider
from investimentos.domain.exceptions import (
    QuoteProviderAuthError,
    QuoteProviderContractError,
    QuoteProviderError,
    QuoteProviderRateLimitedError,
    QuoteProviderTimeoutError,
)
from investimentos.domain.model.ticker import Ticker
from tests.conftest import BRAPI_BASE_URL, QUOTE_PATH, QUOTE_URL

PETR4, ITSA4, VALE3 = Ticker("PETR4"), Ticker("ITSA4"), Ticker("VALE3")


def _provider(client: httpx.AsyncClient, token: str | None = "token-de-teste"):
    return BrapiQuoteProvider(client=client, quote_path=QUOTE_PATH, token=token)


@pytest.fixture
async def http_client():
    async with httpx.AsyncClient(base_url=BRAPI_BASE_URL, timeout=2.0) as client:
        yield client


@respx.mock
async def test_uma_chamada_so_com_os_codigos_separados_por_virgula(
    http_client, payload_v2
) -> None:
    """FR-006, ADR-009 — é isto que transforma N consultas em uma."""
    rota = respx.get(QUOTE_URL).mock(
        return_value=httpx.Response(200, json=payload_v2("PETR4", "ITSA4", "VALE3"))
    )

    quotes = await _provider(http_client).fetch_many([PETR4, ITSA4, VALE3])

    assert rota.call_count == 1
    assert rota.calls.last.request.url.params["symbols"] == "PETR4,ITSA4,VALE3"
    assert len(quotes) == 3


@respx.mock
async def test_lista_vazia_nao_chama_a_fonte(http_client) -> None:
    rota = respx.get(url__startswith=BRAPI_BASE_URL)
    assert await _provider(http_client).fetch_many([]) == {}
    assert rota.call_count == 0


@respx.mock
async def test_token_vai_no_header_e_nunca_na_url(http_client, payload_v2) -> None:
    """Artigo V."""
    rota = respx.get(QUOTE_URL).mock(return_value=httpx.Response(200, json=payload_v2("PETR4")))

    await _provider(http_client, token="segredo-super-secreto").fetch_many([PETR4])

    req = rota.calls.last.request
    assert req.headers["Authorization"] == "Bearer segredo-super-secreto"
    assert "segredo-super-secreto" not in str(req.url)


@respx.mock
@pytest.mark.parametrize(
    ("status", "esperada"),
    [
        (401, QuoteProviderAuthError),
        (403, QuoteProviderAuthError),
        (429, QuoteProviderRateLimitedError),
        (500, QuoteProviderError),
        (418, QuoteProviderError),
    ],
)
async def test_status_da_fonte_vira_excecao_de_dominio(http_client, status, esperada) -> None:
    respx.get(QUOTE_URL).mock(return_value=httpx.Response(status, json={}))
    with pytest.raises(esperada):
        await _provider(http_client).fetch_many([PETR4])


@respx.mock
async def test_404_devolve_mapa_vazio_em_vez_de_derrubar_o_lote(http_client) -> None:
    """ADR-010 — num lote, código desconhecido não é motivo para falhar tudo."""
    respx.get(QUOTE_URL).mock(return_value=httpx.Response(404, text="not found"))

    assert await _provider(http_client).fetch_many([Ticker("ZZZZ9")]) == {}


@respx.mock
async def test_retry_after_e_repassado_na_excecao(http_client) -> None:
    """FR-013, ADR-013 — a espera é informada, não obedecida em silêncio."""
    respx.get(QUOTE_URL).mock(
        return_value=httpx.Response(429, json={}, headers={"Retry-After": "42"})
    )

    with pytest.raises(QuoteProviderRateLimitedError) as exc:
        await _provider(http_client).fetch_many([PETR4])

    assert exc.value.retry_after == 42


@respx.mock
async def test_retry_after_ausente_ou_ilegivel_nao_quebra(http_client) -> None:
    respx.get(QUOTE_URL).mock(
        return_value=httpx.Response(429, json={}, headers={"Retry-After": "Wed, 21 Oct 2026"})
    )

    with pytest.raises(QuoteProviderRateLimitedError) as exc:
        await _provider(http_client).fetch_many([PETR4])

    assert exc.value.retry_after is None


@respx.mock
async def test_corpo_nao_json_vira_erro_de_contrato(http_client) -> None:
    respx.get(QUOTE_URL).mock(return_value=httpx.Response(200, text="<html>manutenção</html>"))
    with pytest.raises(QuoteProviderContractError):
        await _provider(http_client).fetch_many([PETR4])


@respx.mock
async def test_timeout_vira_excecao_de_timeout(http_client) -> None:
    respx.get(QUOTE_URL).mock(side_effect=httpx.ReadTimeout("demorou"))
    with pytest.raises(QuoteProviderTimeoutError):
        await _provider(http_client).fetch_many([PETR4])


@respx.mock
async def test_falha_de_rede_vira_erro_da_fonte(http_client) -> None:
    respx.get(QUOTE_URL).mock(side_effect=httpx.ConnectError("sem rota"))
    with pytest.raises(QuoteProviderError):
        await _provider(http_client).fetch_many([PETR4])


@respx.mock
async def test_mensagem_de_erro_de_auth_nao_vaza_o_token(http_client) -> None:
    respx.get(QUOTE_URL).mock(return_value=httpx.Response(401, json={}))
    with pytest.raises(QuoteProviderAuthError) as exc:
        await _provider(http_client, token="segredo-super-secreto").fetch_many([PETR4])
    assert "segredo-super-secreto" not in str(exc.value)


@respx.mock
async def test_endpoint_legado_continua_funcionando(http_client, brapi_legacy_payload) -> None:
    """ADR-004 — voltar de geração é mudar variável de ambiente."""
    respx.get(f"{BRAPI_BASE_URL}/api/quote/PETR4").mock(
        return_value=httpx.Response(200, json=brapi_legacy_payload)
    )
    provider = BrapiQuoteProvider(
        client=http_client, quote_path="/api/quote/{ticker}", token="token-de-teste"
    )

    quotes = await provider.fetch_many([PETR4])

    assert quotes[PETR4].symbol == "PETR4"
