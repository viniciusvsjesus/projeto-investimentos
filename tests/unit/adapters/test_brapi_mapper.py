"""T030 — Mapper BRAPI → domínio (RF-04, ADR-003, ADR-004)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from investimentos.adapters.outbound.brapi.mapper import (
    extract_first_item,
    normalize_item,
    to_quote,
)
from investimentos.domain.exceptions import QuoteProviderContractError
from investimentos.domain.model.ticker import Ticker

TICKER = Ticker("PETR4")


def test_mapeia_o_formato_legado(brapi_legacy_payload) -> None:
    item = extract_first_item(brapi_legacy_payload)
    assert item is not None
    quote = to_quote(item, TICKER)

    assert quote.symbol == "PETR4"
    assert quote.short_name == "PETR4"
    assert quote.long_name == "Petroleo Brasileiro SA Petrobras"
    assert quote.currency == "BRL"
    assert quote.price == Decimal("36.65")
    assert quote.change == Decimal("-0.35")
    assert quote.change_percent == Decimal("-0.95")
    assert quote.volume == 27681100
    assert quote.market_cap == Decimal("483937892568")
    assert quote.quoted_at.tzinfo is not None


def test_mapeia_o_formato_v2_aninhado(brapi_v2_payload) -> None:
    """ADR-004 — as duas gerações da BRAPI produzem o mesmo Quote."""
    item = extract_first_item(brapi_v2_payload)
    assert item is not None
    quote = to_quote(item, TICKER)

    assert quote.symbol == "PETR4"
    assert quote.price == Decimal("36.65")


def test_mapeia_o_payload_real_do_painel_da_brapi(brapi_v2_payload_real) -> None:
    """Regressão contra o JSON copiado do painel em 2026-09-03."""
    item = extract_first_item(brapi_v2_payload_real)
    assert item is not None
    quote = to_quote(item, Ticker("B3SA3"))

    assert quote.symbol == "B3SA3"
    assert quote.short_name == "B3SA3"
    assert quote.long_name == "B3 SA - Brasil, Bolsa, Balcao"
    assert quote.currency == "BRL"
    assert quote.price == Decimal("17.26")
    assert quote.change == Decimal("0.64")
    assert quote.change_percent == Decimal("3.85")
    assert quote.volume == 41077700
    assert quote.market_cap == Decimal("80748160464")
    assert quote.quoted_at.isoformat() == "2026-09-03T03:54:59+00:00"


def test_symbol_do_v2_esta_fora_de_data_e_sobrevive_a_normalizacao(
    brapi_v2_payload_real,
) -> None:
    """No v2, 'symbol' fica no nível externo: descartá-lo perderia o código."""
    item = extract_first_item(brapi_v2_payload_real)
    assert item is not None
    assert item["symbol"] == "B3SA3"
    assert item["regularMarketPrice"] == 17.26


def test_data_vence_o_nivel_externo_em_caso_de_conflito() -> None:
    item = normalize_item({"symbol": "FORA", "data": {"symbol": "DENTRO"}})
    assert item["symbol"] == "DENTRO"


def test_as_duas_geracoes_produzem_o_mesmo_resultado(
    brapi_legacy_payload, brapi_v2_payload
) -> None:
    legado = to_quote(extract_first_item(brapi_legacy_payload), TICKER)  # type: ignore[arg-type]
    v2 = to_quote(extract_first_item(brapi_v2_payload), TICKER)  # type: ignore[arg-type]
    assert legado == v2


def test_preco_nao_herda_erro_de_ponto_flutuante() -> None:
    """ADR-003 — Decimal(str(v)), nunca Decimal(float)."""
    quote = to_quote({"symbol": "PETR4", "regularMarketPrice": 0.1}, TICKER)
    assert quote.price == Decimal("0.1")
    assert quote.price + Decimal("0.2") == Decimal("0.3")


def test_campos_opcionais_ausentes_viram_none() -> None:
    quote = to_quote({"symbol": "PETR4", "regularMarketPrice": 10.0}, TICKER)
    assert quote.long_name is None
    assert quote.change is None
    assert quote.change_percent is None
    assert quote.volume is None
    assert quote.market_cap is None


def test_moeda_ausente_assume_brl() -> None:
    quote = to_quote({"symbol": "PETR4", "regularMarketPrice": 10.0}, TICKER)
    assert quote.currency == "BRL"


def test_instante_ausente_assume_agora_em_utc() -> None:
    quote = to_quote({"symbol": "PETR4", "regularMarketPrice": 10.0}, TICKER)
    assert quote.quoted_at.tzinfo is not None


def test_preco_ausente_e_erro_de_contrato() -> None:
    """Dado ausente vira erro explícito — nunca cotação com preço zero."""
    with pytest.raises(QuoteProviderContractError):
        to_quote({"symbol": "PETR4"}, TICKER)


def test_simbolo_ausente_usa_o_ticker_pedido() -> None:
    quote = to_quote({"regularMarketPrice": 10.0}, TICKER)
    assert quote.symbol == "PETR4"


def test_simbolo_fora_do_padrao_cai_para_o_ticker_pedido() -> None:
    quote = to_quote({"symbol": "^BVSP", "regularMarketPrice": 10.0}, TICKER)
    assert quote.symbol == "PETR4"


def test_campos_desconhecidos_sao_ignorados() -> None:
    """A fonte pode crescer sem quebrar a nossa API — é o isolamento do RF-04."""
    quote = to_quote(
        {"symbol": "PETR4", "regularMarketPrice": 10.0, "campoNovoDaBrapi": {"x": 1}}, TICKER
    )
    assert quote.price == Decimal("10.0")


def test_results_vazio_devolve_none() -> None:
    assert extract_first_item({"results": []}) is None


def test_results_ausente_e_erro_de_contrato() -> None:
    with pytest.raises(QuoteProviderContractError):
        extract_first_item({"requestedAt": "2026-09-03T17:25:28.170Z"})


def test_payload_que_nao_e_objeto_e_erro_de_contrato() -> None:
    with pytest.raises(QuoteProviderContractError):
        extract_first_item(["isto não é um objeto"])


def test_item_que_nao_e_objeto_e_erro_de_contrato() -> None:
    with pytest.raises(QuoteProviderContractError):
        normalize_item("texto solto")
