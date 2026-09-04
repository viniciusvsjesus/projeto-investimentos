"""T061 — Corpo de erro padronizado em toda a API (RF-10, Artigo VIII)."""

from __future__ import annotations

import httpx
import pytest
import respx

from tests.conftest import BRAPI_BASE_URL

QUOTE_URL = f"{BRAPI_BASE_URL}/api/v2/stocks/quote"
CAMPOS = {"type", "title", "status", "detail", "instance"}


@respx.mock
@pytest.mark.parametrize(
    ("mock", "status_esperado"),
    [
        (httpx.Response(404, json={}), 404),
        (httpx.Response(401, json={}), 502),
        (httpx.Response(429, json={}), 503),
        (httpx.Response(500, json={}), 502),
    ],
)
def test_todo_erro_usa_o_mesmo_formato(client, mock, status_esperado) -> None:
    respx.get(QUOTE_URL, params={"symbols": "PETR4"}).mock(return_value=mock)

    resposta = client.get("/cotacao/PETR4")

    assert resposta.status_code == status_esperado
    corpo = resposta.json()
    assert CAMPOS.issubset(corpo.keys())
    assert corpo["status"] == status_esperado
    assert corpo["type"].startswith("https://projeto-investimentos/errors/")
    assert corpo["instance"] == "/cotacao/PETR4"


def test_erro_de_validacao_tambem_usa_o_formato(client) -> None:
    corpo = client.get("/cotacao/PETR").json()
    assert CAMPOS.issubset(corpo.keys())
    assert corpo["status"] == 400
    assert corpo["type"].endswith("/invalid-ticker")


def test_erro_usa_o_content_type_de_problem_details(client) -> None:
    resposta = client.get("/cotacao/PETR")
    assert resposta.headers["content-type"].startswith("application/problem+json")


@respx.mock
def test_erro_nao_vaza_stack_trace_nem_detalhe_interno(client) -> None:
    respx.get(QUOTE_URL, params={"symbols": "PETR4"}).mock(
        return_value=httpx.Response(500, json={})
    )
    texto = client.get("/cotacao/PETR4").text

    for proibido in ("Traceback", "File \"/", "httpx.", "site-packages"):
        assert proibido not in texto
