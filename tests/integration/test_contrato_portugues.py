"""T014-T016 — O contrato fala português (FR-004, FR-005, FR-006)."""

from __future__ import annotations

import httpx
import respx

from tests.conftest import QUOTE_URL

# Os nomes que a Spec 002 publicava. Nenhum pode sobreviver em resposta alguma.
NOMES_ANTIGOS = {
    "shortName",
    "longName",
    "currency",
    "price",
    "change",
    "changePercent",
    "marketCap",
    "quotedAt",
    "source",
    "cached",
    "dependencies",
}


def _rota(*codigos: str):
    return respx.get(QUOTE_URL, params={"symbols": ",".join(codigos)})


def _chaves(obj, encontradas: set[str] | None = None) -> set[str]:
    """Varre a resposta inteira, incluindo objetos aninhados."""
    encontradas = encontradas if encontradas is not None else set()
    if isinstance(obj, dict):
        for chave, valor in obj.items():
            encontradas.add(chave)
            _chaves(valor, encontradas)
    elif isinstance(obj, list):
        for item in obj:
            _chaves(item, encontradas)
    return encontradas


@respx.mock
def test_item_nao_tem_campo_em_ingles(client, payload_v2) -> None:
    _rota("ITSA4").mock(return_value=httpx.Response(200, json=payload_v2("ITSA4")))

    vazamentos = _chaves(client.get("/acoes/ITSA4").json()) & NOMES_ANTIGOS

    assert not vazamentos, f"campos ainda em inglês: {sorted(vazamentos)}"


@respx.mock
def test_lista_nao_tem_campo_em_ingles(client, payload_v2) -> None:
    _rota("ITSA4", "PETR4").mock(
        return_value=httpx.Response(200, json=payload_v2("ITSA4", "PETR4"))
    )

    vazamentos = _chaves(client.get("/acoes?ticker=ITSA4&ticker=PETR4").json()) & NOMES_ANTIGOS

    assert not vazamentos, f"campos ainda em inglês: {sorted(vazamentos)}"


@respx.mock
def test_item_tem_todos_os_campos_em_portugues(client, payload_v2) -> None:
    _rota("ITSA4").mock(return_value=httpx.Response(200, json=payload_v2("ITSA4")))

    corpo = client.get("/acoes/ITSA4").json()

    esperados = {
        "ticker",
        "nomeCurto",
        "nomeLongo",
        "moeda",
        "preco",
        "variacao",
        "variacaoPercentual",
        "volume",
        "valorDeMercado",
        "cotadoEm",
        "fonte",
        "emCache",
    }
    assert esperados == set(corpo)


@respx.mock
def test_situacao_usa_valores_em_portugues(client, payload_v2) -> None:
    """FR-005."""
    _rota("ITSA4", "ZZZZ9").mock(return_value=httpx.Response(200, json=payload_v2("ITSA4")))

    corpo = client.get("/acoes?ticker=ITSA4&ticker=ZZZZ9").json()

    situacoes = {item["ticker"]: item["situacao"] for item in corpo}
    assert situacoes == {"ITSA4": "encontrada", "ZZZZ9": "naoEncontrada"}


def test_indice_e_saude_em_portugues(client) -> None:
    indice = client.get("/").json()
    assert {"servico", "versao", "situacao", "exemplo", "rotas"} == set(indice)
    assert {"acao", "acoes", "saude", "openapi", "documentacao"} == set(indice["rotas"])

    saude = client.get("/health").json()
    assert {"situacao", "dependencias"} == set(saude)


def test_erro_mantem_os_nomes_do_rfc_9457(client) -> None:
    """FR-006, ADR-017 — traduzir estes campos quebraria o problem+json.

    Os nomes são do padrão; os valores é que falam português.
    """
    resposta = client.get("/acoes/PETR")

    assert resposta.headers["content-type"].startswith("application/problem+json")
    corpo = resposta.json()
    assert {"type", "title", "status", "detail", "instance"} == set(corpo)
    assert corpo["title"] == "Código de ativo inválido"
    assert "quatro caracteres" in corpo["detail"]
