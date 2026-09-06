"""T003 — TooManyTickersError."""

from __future__ import annotations

import pytest

from investimentos.domain.exceptions import DomainError, TooManyTickersError


def test_carrega_os_numeros() -> None:
    """A mensagem tem que ser útil sem o adapter recalcular nada."""
    erro = TooManyTickersError(requested=5, limit=3)
    assert erro.requested == 5
    assert erro.limit == 3


def test_mensagem_diz_o_pedido_e_o_limite() -> None:
    mensagem = TooManyTickersError(requested=5, limit=3).message
    assert "5" in mensagem
    assert "3" in mensagem


def test_e_erro_de_dominio() -> None:
    """A cota é regra do problema, não detalhe de HTTP."""
    with pytest.raises(DomainError):
        raise TooManyTickersError(requested=4, limit=3)
