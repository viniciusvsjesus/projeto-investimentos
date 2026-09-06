"""T010 e transversais — GET /acoes: vários ativos, uma lista."""

from __future__ import annotations

import httpx
import respx
from fastapi.testclient import TestClient

from investimentos.adapters.inbound.http.app import create_app
from investimentos.adapters.inbound.http.dependencies import get_quotes_use_case
from investimentos.adapters.outbound.brapi.client import BrapiQuoteProvider
from investimentos.application.usecases.get_quote import GetQuotesUseCase
from tests.conftest import BRAPI_BASE_URL, QUOTE_URL, InMemoryQuoteCache


def _rota(*codigos: str):
    return respx.get(QUOTE_URL, params={"symbols": ",".join(codigos)})


@respx.mock
def test_consulta_tres_ativos(client, payload_v2) -> None:
    """US1-1, SC-001 — três cotações, uma chamada."""
    rota = _rota("ITSA4", "PETR4", "VALE3").mock(
        return_value=httpx.Response(200, json=payload_v2("ITSA4", "PETR4", "VALE3"))
    )

    resposta = client.get("/acoes?ticker=ITSA4&ticker=PETR4&ticker=VALE3")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert isinstance(corpo, list)
    assert [item["ticker"] for item in corpo] == ["ITSA4", "PETR4", "VALE3"]
    assert all(item["situacao"] == "encontrada" for item in corpo)
    assert rota.call_count == 1


@respx.mock
def test_um_ativo_continua_sendo_lista(client, payload_v2) -> None:
    """US1-2, Artigo XI — coleção não muda de forma por causa da quantidade."""
    _rota("PETR4").mock(return_value=httpx.Response(200, json=payload_v2("PETR4")))

    corpo = client.get("/acoes?ticker=PETR4").json()

    assert isinstance(corpo, list)
    assert len(corpo) == 1


@respx.mock
def test_preserva_a_ordem_pedida(client, payload_v2) -> None:
    """FR-016 — a fonte devolve em outra ordem; a nossa resposta não."""
    _rota("VALE3", "PETR4").mock(
        return_value=httpx.Response(200, json=payload_v2("PETR4", "VALE3"))
    )

    corpo = client.get("/acoes?ticker=VALE3&ticker=PETR4").json()

    assert [item["ticker"] for item in corpo] == ["VALE3", "PETR4"]


@respx.mock
def test_repeticao_nao_duplica(client, payload_v2) -> None:
    """US1-3."""
    _rota("PETR4").mock(return_value=httpx.Response(200, json=payload_v2("PETR4")))

    corpo = client.get("/acoes?ticker=petr4&ticker=PETR4").json()

    assert len(corpo) == 1
    assert corpo[0]["ticker"] == "PETR4"


@respx.mock
def test_a_cotacao_vem_envelopada_com_todos_os_campos(client, payload_v2) -> None:
    """FR-015 — o que se sabe de cada ativo não muda."""
    _rota("PETR4").mock(return_value=httpx.Response(200, json=payload_v2("PETR4")))

    item = client.get("/acoes?ticker=PETR4").json()[0]

    q = item["cotacao"]
    for campo in ("ticker", "nomeCurto", "moeda", "preco", "cotadoEm", "fonte", "emCache"):
        assert campo in q, f"campo ausente: {campo}"
    assert isinstance(q["preco"], int | float)


@respx.mock
def test_inexistente_volta_marcado_ao_lado_dos_que_deram_certo(client, payload_v2) -> None:
    """FR-011, ADR-012 — na coleção, não encontrado é resultado."""
    _rota("PETR4", "ZZZZ9").mock(
        return_value=httpx.Response(200, json=payload_v2("PETR4"))
    )

    corpo = client.get("/acoes?ticker=PETR4&ticker=ZZZZ9").json()

    por_codigo = {item["ticker"]: item for item in corpo}
    assert por_codigo["PETR4"]["situacao"] == "encontrada"
    assert por_codigo["ZZZZ9"]["situacao"] == "naoEncontrada"
    assert por_codigo["ZZZZ9"]["cotacao"] is None


@respx.mock
def test_formato_invalido_derruba_tudo_sem_chamar_a_fonte(client) -> None:
    """FR-011, SC-005 — erro de quem chamou não é resultado de busca."""
    rota = respx.get(url__startswith=BRAPI_BASE_URL)

    resposta = client.get("/acoes?ticker=PETR4&ticker=PETR")

    assert resposta.status_code == 400
    assert rota.call_count == 0
    assert "quatro caracteres" in resposta.json()["detail"]


@respx.mock
def test_acima_do_limite_devolve_400_explicando(client) -> None:
    """FR-010."""
    rota = respx.get(url__startswith=BRAPI_BASE_URL)

    resposta = client.get("/acoes?ticker=PETR4&ticker=ITSA4&ticker=VALE3&ticker=BOVA11")

    assert resposta.status_code == 400
    assert rota.call_count == 0
    corpo = resposta.json()
    assert corpo["type"].endswith("/too-many-tickers")
    assert "3" in corpo["detail"]


def test_sem_nenhum_ativo_devolve_400(client) -> None:
    assert client.get("/acoes").status_code == 400


@respx.mock
def test_segunda_consulta_marca_origem_por_ativo(test_settings, payload_v2) -> None:
    """SC-006, US2-5 — dá para saber a origem sem olhar log nem cache."""
    rota_itsa = _rota("ITSA4").mock(
        return_value=httpx.Response(200, json=payload_v2("ITSA4"))
    )
    rota_petr = _rota("PETR4").mock(
        return_value=httpx.Response(200, json=payload_v2("PETR4"))
    )

    app = create_app(test_settings)
    with TestClient(app) as c:
        cache = InMemoryQuoteCache()
        provider = BrapiQuoteProvider(
            client=app.state.container._http_client,  # montagem de teste
            quote_path=test_settings.brapi_quote_path,
            token=test_settings.brapi_token_value,
        )
        app.dependency_overrides[get_quotes_use_case] = lambda: GetQuotesUseCase(
            provider, cache, max_tickers=3
        )

        c.get("/acoes?ticker=ITSA4")           # aquece o cache com um ativo
        corpo = c.get("/acoes?ticker=ITSA4&ticker=PETR4").json()

    por_codigo = {item["ticker"]: item for item in corpo}
    assert por_codigo["ITSA4"]["cotacao"]["emCache"] is True
    assert por_codigo["PETR4"]["cotacao"]["emCache"] is False
    # SC-004: a fonte nunca viu ITSA4 na segunda chamada
    assert rota_itsa.call_count == 1
    assert rota_petr.call_count == 1
    assert rota_petr.calls.last.request.url.params["symbols"] == "PETR4"


@respx.mock
def test_cota_esgotada_repassa_o_retry_after(client) -> None:
    """FR-013, ADR-013."""
    _rota("PETR4").mock(
        return_value=httpx.Response(429, json={}, headers={"Retry-After": "30"})
    )

    resposta = client.get("/acoes?ticker=PETR4")

    assert resposta.status_code == 503
    assert resposta.headers["Retry-After"] == "30"
