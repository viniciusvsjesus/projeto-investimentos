"""T009, T011 — GET /acoes/{ticker}: um ativo, um objeto (US1)."""

from __future__ import annotations

import httpx
import respx

from tests.conftest import QUOTE_URL


def _rota(ticker: str = "PETR4"):
    return respx.get(QUOTE_URL, params={"symbols": ticker})


@respx.mock
def test_devolve_um_objeto_e_nao_lista(client, payload_v2) -> None:
    """Artigo XI — item devolve objeto."""
    _rota().mock(return_value=httpx.Response(200, json=payload_v2("PETR4")))

    corpo = client.get("/acoes/PETR4").json()

    assert isinstance(corpo, dict)
    assert corpo["ticker"] == "PETR4"
    assert corpo["preco"] == 36.65
    assert corpo["emCache"] is False


@respx.mock
def test_aceita_minusculas(client, payload_v2) -> None:
    rota = _rota().mock(return_value=httpx.Response(200, json=payload_v2("PETR4")))

    assert client.get("/acoes/petr4").json()["ticker"] == "PETR4"
    assert rota.calls.last.request.url.params["symbols"] == "PETR4"


@respx.mock
def test_ativo_inexistente_devolve_404(client) -> None:
    """ADR-012 — no item, não encontrado é ausência do recurso."""
    respx.get(QUOTE_URL, params={"symbols": "ZZZZ9"}).mock(
        return_value=httpx.Response(200, json={"results": []})
    )

    assert client.get("/acoes/ZZZZ9").status_code == 404


@respx.mock
def test_formato_invalido_devolve_400_sem_chamar_a_fonte(client) -> None:
    rota = respx.get(url__startswith="https://brapi.test")

    resposta = client.get("/acoes/PETR")

    assert resposta.status_code == 400
    assert rota.call_count == 0


def test_rota_antiga_sumiu(client) -> None:
    """FR-017 — a quebra é deliberada e registrada."""
    assert client.get("/cotacao/PETR4").status_code == 404


@respx.mock
def test_timeout_da_fonte_devolve_504(client) -> None:
    _rota().mock(side_effect=httpx.ReadTimeout("demorou"))
    assert client.get("/acoes/PETR4").status_code == 504
