"""T009 — Mapper BRAPI → domínio (FR-004 da Spec 001, ADR-014 da Spec 002)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from investimentos.adapters.outbound.brapi.mapper import (
    extract_items,
    normalize_item,
    to_quote,
    to_quotes,
)
from investimentos.domain.exceptions import QuoteProviderContractError
from investimentos.domain.model.ticker import Ticker

PETR4, ITSA4, VALE3 = Ticker("PETR4"), Ticker("ITSA4"), Ticker("VALE3")


def test_mapeia_varios_ativos_de_uma_vez(payload_v2) -> None:
    quotes = to_quotes(payload_v2("PETR4", "ITSA4", "VALE3"), [PETR4, ITSA4, VALE3])

    assert set(quotes) == {PETR4, ITSA4, VALE3}
    assert quotes[PETR4].price == Decimal("36.65")


def test_casa_por_codigo_e_nao_por_posicao(payload_v2) -> None:
    """ADR-014 — a fonte pode devolver em qualquer ordem.

    Se o casamento fosse por índice, PETR4 receberia a cotação de VALE3 — um
    defeito que passa despercebido porque a resposta parece válida.
    """
    payload = payload_v2("VALE3", "PETR4")
    payload["results"][0]["data"]["regularMarketPrice"] = 99.99

    quotes = to_quotes(payload, [PETR4, VALE3])

    assert quotes[VALE3].price == Decimal("99.99")
    assert quotes[PETR4].price == Decimal("36.65")


def test_ativo_ausente_da_resposta_simplesmente_nao_vem(payload_v2) -> None:
    """FR-011 — ausência no mapa é a informação de 'não encontrado'."""
    quotes = to_quotes(payload_v2("PETR4"), [PETR4, Ticker("ZZZZ9")])

    assert PETR4 in quotes
    assert Ticker("ZZZZ9") not in quotes


def test_item_nao_pedido_e_ignorado(payload_v2) -> None:
    """A fonte pode devolver algo a mais; não pode estragar quem foi pedido."""
    quotes = to_quotes(payload_v2("PETR4", "VALE3"), [PETR4])

    assert set(quotes) == {PETR4}


def test_simbolo_fora_do_padrao_e_ignorado_sem_derrubar_o_lote(payload_v2) -> None:
    payload = payload_v2("PETR4")
    payload["results"].append({"symbol": "^BVSP", "data": {"regularMarketPrice": 1.0}})

    quotes = to_quotes(payload, [PETR4])

    assert set(quotes) == {PETR4}


def test_resposta_vazia_devolve_mapa_vazio() -> None:
    assert to_quotes({"results": []}, [PETR4]) == {}


def test_mapeia_o_payload_real_do_painel_da_brapi(brapi_v2_payload_real) -> None:
    b3sa3 = Ticker("B3SA3")
    quotes = to_quotes(brapi_v2_payload_real, [b3sa3])

    q = quotes[b3sa3]
    assert q.long_name == "B3 SA - Brasil, Bolsa, Balcao"
    assert q.price == Decimal("17.26")
    assert q.change_percent == Decimal("3.85")
    assert q.quoted_at.isoformat() == "2026-09-03T03:54:59+00:00"


def test_formato_legado_continua_funcionando(brapi_legacy_payload) -> None:
    """ADR-004 — as duas gerações produzem o mesmo resultado."""
    quotes = to_quotes(brapi_legacy_payload, [PETR4])

    assert quotes[PETR4].price == Decimal("36.65")


def test_symbol_do_v2_esta_fora_de_data_e_sobrevive_a_normalizacao(
    brapi_v2_payload_real,
) -> None:
    item = extract_items(brapi_v2_payload_real)[0]
    assert item["symbol"] == "B3SA3"
    assert item["regularMarketPrice"] == 17.26


def test_data_vence_o_nivel_externo_em_caso_de_conflito() -> None:
    assert normalize_item({"symbol": "FORA", "data": {"symbol": "DENTRO"}})["symbol"] == "DENTRO"


def test_preco_nao_herda_erro_de_ponto_flutuante() -> None:
    """ADR-003 — Decimal(str(v)), nunca Decimal(float)."""
    q = to_quote({"symbol": "PETR4", "regularMarketPrice": 0.1}, PETR4)
    assert q.price + Decimal("0.2") == Decimal("0.3")


def test_preco_ausente_e_erro_de_contrato() -> None:
    with pytest.raises(QuoteProviderContractError):
        to_quote({"symbol": "PETR4"}, PETR4)


def test_results_ausente_e_erro_de_contrato() -> None:
    with pytest.raises(QuoteProviderContractError):
        extract_items({"requestedAt": "2026-09-06T12:12:29.182Z"})


def test_payload_que_nao_e_objeto_e_erro_de_contrato() -> None:
    with pytest.raises(QuoteProviderContractError):
        extract_items(["isto não é um objeto"])
