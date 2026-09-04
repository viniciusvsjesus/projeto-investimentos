"""T060 — Rota /cotacao/{ticker} ponta a ponta, BRAPI interceptada (RF-01…RF-05)."""

from __future__ import annotations

import httpx
import respx
from fastapi.testclient import TestClient

from investimentos.adapters.inbound.http.app import create_app
from investimentos.adapters.inbound.http.dependencies import get_quote_use_case
from investimentos.adapters.outbound.brapi.client import BrapiQuoteProvider
from investimentos.application.usecases.get_quote import GetQuoteUseCase
from tests.conftest import BRAPI_BASE_URL, InMemoryQuoteCache

QUOTE_URL = f"{BRAPI_BASE_URL}/api/v2/stocks/quote"


def _rota(ticker: str = "PETR4"):
    return respx.get(QUOTE_URL, params={"symbols": ticker})


@respx.mock
def test_retorna_cotacao(client, brapi_v2_payload) -> None:
    """CA-01.1 — todos os campos do contrato presentes na resposta."""
    _rota().mock(return_value=httpx.Response(200, json=brapi_v2_payload))

    resposta = client.get("/cotacao/PETR4")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["ticker"] == "PETR4"
    assert corpo["shortName"] == "PETR4"
    assert corpo["longName"] == "Petroleo Brasileiro SA Petrobras"
    assert corpo["currency"] == "BRL"
    assert corpo["price"] == 36.65
    assert corpo["changePercent"] == -0.95
    assert corpo["volume"] == 27681100
    assert corpo["source"] == "brapi"
    assert corpo["cached"] is False
    assert corpo["quotedAt"].startswith("2026-09-03T17:24:54")


@respx.mock
def test_retorna_cotacao_com_o_payload_real_da_brapi(client, brapi_v2_payload_real) -> None:
    """Regressão contra o JSON copiado do painel da BRAPI, sem rede e sem token."""
    _rota("B3SA3").mock(return_value=httpx.Response(200, json=brapi_v2_payload_real))

    corpo = client.get("/cotacao/B3SA3").json()

    assert corpo["ticker"] == "B3SA3"
    assert corpo["longName"] == "B3 SA - Brasil, Bolsa, Balcao"
    assert corpo["price"] == 17.26
    assert corpo["change"] == 0.64
    assert corpo["changePercent"] == 3.85
    assert corpo["volume"] == 41077700
    assert corpo["marketCap"] == 80748160464
    assert corpo["quotedAt"].startswith("2026-09-03T03:54:59")


@respx.mock
def test_resposta_usa_camel_case(client, brapi_v2_payload) -> None:
    """RF-04 — o contrato é nosso: camelCase na fronteira, snake_case no Python."""
    _rota().mock(return_value=httpx.Response(200, json=brapi_v2_payload))
    corpo = client.get("/cotacao/PETR4").json()

    assert "shortName" in corpo and "short_name" not in corpo
    assert "changePercent" in corpo and "change_percent" not in corpo
    assert "quotedAt" in corpo and "quoted_at" not in corpo


@respx.mock
def test_campos_extras_da_brapi_nao_vazam_para_a_nossa_resposta(
    client, brapi_v2_payload_real
) -> None:
    """RF-04 — logourl, fiftyTwoWeekRange e afins são da BRAPI, não do nosso contrato."""
    _rota("B3SA3").mock(return_value=httpx.Response(200, json=brapi_v2_payload_real))
    corpo = client.get("/cotacao/B3SA3").json()

    for campo in ("logourl", "fiftyTwoWeekRange", "regularMarketDayRange", "requestedSymbol"):
        assert campo not in corpo


@respx.mock
def test_aceita_ticker_em_minusculas(client, brapi_v2_payload) -> None:
    """CA-01.4 / RF-03."""
    rota = _rota().mock(return_value=httpx.Response(200, json=brapi_v2_payload))

    resposta = client.get("/cotacao/petr4")

    assert resposta.status_code == 200
    assert resposta.json()["ticker"] == "PETR4"
    assert rota.calls.last.request.url.params["symbols"] == "PETR4"


@respx.mock
def test_formato_invalido_nao_chama_a_fonte(client) -> None:
    """CA-01.2 / RF-02 — rejeita na borda, antes de gastar cota da BRAPI."""
    rota = respx.get(url__startswith=BRAPI_BASE_URL)

    resposta = client.get("/cotacao/PETR")

    assert resposta.status_code == 400
    assert rota.call_count == 0
    assert "quatro caracteres" in resposta.json()["detail"]


@respx.mock
def test_ativo_inexistente_devolve_404(client) -> None:
    """CA-01.3."""
    _rota("ZZZZ9").mock(return_value=httpx.Response(200, json={"results": []}))
    assert client.get("/cotacao/ZZZZ9").status_code == 404


@respx.mock
def test_segunda_consulta_vem_do_cache(test_settings, brapi_v2_payload) -> None:
    """CA-01.5 / RF-05 — a fonte é chamada uma vez só."""
    rota = _rota().mock(return_value=httpx.Response(200, json=brapi_v2_payload))

    app = create_app(test_settings)
    with TestClient(app) as client:
        cache = InMemoryQuoteCache()
        provider = BrapiQuoteProvider(
            client=app.state.container._http_client,  # montagem de teste
            quote_path=test_settings.brapi_quote_path,
            token=test_settings.brapi_token_value,
        )
        app.dependency_overrides[get_quote_use_case] = lambda: GetQuoteUseCase(provider, cache)

        primeira = client.get("/cotacao/PETR4")
        segunda = client.get("/cotacao/PETR4")

    assert primeira.json()["cached"] is False
    assert segunda.json()["cached"] is True
    assert rota.call_count == 1


@respx.mock
def test_timeout_da_fonte_devolve_504(client) -> None:
    _rota().mock(side_effect=httpx.ReadTimeout("demorou"))
    assert client.get("/cotacao/PETR4").status_code == 504


@respx.mock
def test_credencial_rejeitada_devolve_502(client) -> None:
    _rota().mock(return_value=httpx.Response(401, json={}))
    assert client.get("/cotacao/PETR4").status_code == 502


@respx.mock
def test_cota_esgotada_devolve_503(client) -> None:
    _rota().mock(return_value=httpx.Response(429, json={}))
    assert client.get("/cotacao/PETR4").status_code == 503


@respx.mock
def test_payload_inesperado_devolve_502(client) -> None:
    """Nunca 200 com corpo vazio: falha de contrato é erro explícito."""
    _rota().mock(
        return_value=httpx.Response(200, json={"results": [{"symbol": "PETR4", "data": {}}]})
    )
    assert client.get("/cotacao/PETR4").status_code == 502


@respx.mock
def test_valores_monetarios_saem_como_numero_json_e_nao_string(client, brapi_v2_payload) -> None:
    """O contrato promete `number`; string quebraria quem faz conta com o valor."""
    _rota().mock(return_value=httpx.Response(200, json=brapi_v2_payload))
    corpo = client.get("/cotacao/PETR4").json()

    for campo in ("price", "change", "changePercent", "marketCap"):
        assert isinstance(corpo[campo], int | float), f"{campo} saiu como {type(corpo[campo])}"
        assert not isinstance(corpo[campo], str)


@respx.mock
def test_campos_opcionais_ausentes_saem_como_null(client) -> None:
    _rota().mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {"symbol": "PETR4", "data": {"regularMarketPrice": 10.5, "currency": "BRL"}}
                ],
                "requestedAt": "2026-09-03T12:12:29.182Z",
            },
        )
    )
    corpo = client.get("/cotacao/PETR4").json()

    assert corpo["price"] == 10.5
    assert corpo["change"] is None
    assert corpo["marketCap"] is None
    assert corpo["longName"] is None
