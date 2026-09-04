"""T011 — Value Object Quote (RN-03, RN-04)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from investimentos.domain.exceptions import QuoteProviderContractError
from investimentos.domain.model.quote import Quote
from investimentos.domain.model.ticker import Ticker


def _quote(**overrides: object) -> Quote:
    base: dict[str, object] = {
        "ticker": Ticker("PETR4"),
        "short_name": "PETR4",
        "currency": "BRL",
        "price": Decimal("36.65"),
        "quoted_at": datetime(2026, 9, 3, 17, 24, 54, tzinfo=timezone.utc),
    }
    base.update(overrides)
    return Quote(**base)  # type: ignore[arg-type]


def test_constroi_com_os_campos_obrigatorios() -> None:
    quote = _quote()
    assert quote.symbol == "PETR4"
    assert quote.price == Decimal("36.65")
    assert quote.long_name is None


def test_rejeita_preco_negativo() -> None:
    with pytest.raises(QuoteProviderContractError):
        _quote(price=Decimal("-1"))


def test_rejeita_moeda_fora_do_iso_4217() -> None:
    with pytest.raises(QuoteProviderContractError):
        _quote(currency="REAL")


def test_rejeita_instante_sem_fuso_horario() -> None:
    """RN-04 — sem fuso não dá para comparar instantes com segurança."""
    with pytest.raises(QuoteProviderContractError):
        _quote(quoted_at=datetime(2026, 9, 3, 17, 24, 54))


def test_preco_usa_decimal_e_nao_float() -> None:
    """RN-03 / ADR-003 — a soma exata é o que float binário não entrega."""
    quote = _quote(price=Decimal("0.1"))
    assert quote.price + Decimal("0.2") == Decimal("0.3")
    assert isinstance(quote.price, Decimal)


def test_e_imutavel() -> None:
    quote = _quote()
    with pytest.raises(FrozenInstanceError):
        quote.price = Decimal("99")  # type: ignore[misc]


def test_igualdade_por_valor() -> None:
    assert _quote() == _quote()
