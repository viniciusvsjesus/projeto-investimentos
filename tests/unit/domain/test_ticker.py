"""T010 — Value Object Ticker (RF-02, RF-03, RN-01, RN-02)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from investimentos.domain.exceptions import InvalidTickerError
from investimentos.domain.model.ticker import Ticker


@pytest.mark.parametrize(
    "codigo",
    [
        "PETR4",   # ação ordinária/preferencial
        "VALE3",
        "ITUB4",
        "BOVA11",  # ETF
        "MXRF11",  # fundo imobiliário
        "TAEE11",  # unit
        "PETR4F",  # mercado fracionário
        "B3SA3",   # dígito no meio do prefixo — a própria B3
        "AAPL34",  # BDR
        "M1TA34",  # BDR com dígito no prefixo
    ],
)
def test_aceita_codigos_validos_da_b3(codigo: str) -> None:
    assert Ticker(codigo).value == codigo


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("petr4", "PETR4"),
        ("PeTr4", "PETR4"),
        ("  vale3  ", "VALE3"),
        ("bova11", "BOVA11"),
        ("b3sa3", "B3SA3"),
    ],
)
def test_normaliza_para_maiusculas(entrada: str, esperado: str) -> None:
    """RN-02 / RF-03 / CA-01.4."""
    assert Ticker(entrada).value == esperado


@pytest.mark.parametrize(
    "codigo",
    [
        "PETR",       # sem dígito final
        "PE4",        # prefixo curto demais
        "B3SA",       # sem dígito final
        "PETRO4",     # prefixo longo demais
        "PETR444",    # dígitos demais
        "PETR4X",     # sufixo inválido
        "PETR-4",     # separador
        "1PET4",      # começa com dígito
        "1234",       # sem letra alguma
        "",           # vazio
        "   ",        # só espaço
        "'; DROP TABLE quotes; --",
    ],
)
def test_rejeita_formato_invalido(codigo: str) -> None:
    """RF-02 / CA-01.2 — a validação acontece antes de qualquer chamada externa."""
    with pytest.raises(InvalidTickerError):
        Ticker(codigo)


def test_rejeita_tipo_nao_textual() -> None:
    with pytest.raises(InvalidTickerError):
        Ticker(1234)  # type: ignore[arg-type]


def test_mensagem_de_erro_explica_o_formato_esperado() -> None:
    with pytest.raises(InvalidTickerError) as exc:
        Ticker("PETR")
    mensagem = exc.value.message
    assert "PETR" in mensagem
    assert "quatro caracteres" in mensagem


def test_e_imutavel() -> None:
    ticker = Ticker("PETR4")
    with pytest.raises(FrozenInstanceError):
        ticker.value = "VALE3"  # type: ignore[misc]


def test_igualdade_e_hash_por_valor() -> None:
    assert Ticker("petr4") == Ticker("PETR4")
    assert len({Ticker("PETR4"), Ticker("petr4")}) == 1
    assert {Ticker("PETR4"): "ok"}[Ticker("petr4")] == "ok"


def test_str_devolve_o_codigo() -> None:
    assert str(Ticker("petr4")) == "PETR4"
