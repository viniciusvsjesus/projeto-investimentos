"""T062 — A raiz devolve o índice em JSON (RF-08, CA-03.1)."""

from __future__ import annotations


def test_raiz_devolve_json(client) -> None:
    """Abrir localhost:8000 no navegador tem que mostrar JSON, não uma tela."""
    resposta = client.get("/")

    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("application/json")


def test_indice_identifica_o_servico(client) -> None:
    corpo = client.get("/").json()

    assert corpo["servico"] == "Projeto Investimentos API"
    assert corpo["situacao"] == "ok"
    assert corpo["versao"]


def test_indice_traz_url_de_exemplo_pronta_para_colar(client) -> None:
    """US3-3 — quem abriu a raiz descobre sozinho como consultar."""
    corpo = client.get("/").json()

    assert corpo["exemplo"].endswith("/acoes/ITSA4")
    assert corpo["exemplo"].startswith("http")


def test_indice_anuncia_as_duas_rotas_novas(client) -> None:
    """US3-3 — e não a antiga."""
    rotas = client.get("/").json()["rotas"]

    assert rotas["acao"] == "/acoes/{ticker}"
    assert rotas["acoes"].startswith("/acoes?ticker=")
    assert rotas["saude"] == "/health"
    assert rotas["openapi"] == "/openapi.json"
    assert "ticker" not in rotas


def test_indice_traz_a_versao_dois(client) -> None:
    """A quebra de contrato do FR-017 é visível na versão."""
    assert client.get("/").json()["versao"].startswith("3.")


def test_a_raiz_nao_redireciona(client) -> None:
    """Decisão Q8 revista: nada de Swagger como porta de entrada."""
    resposta = client.get("/", follow_redirects=False)
    assert resposta.status_code == 200
