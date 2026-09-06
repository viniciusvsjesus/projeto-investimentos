"""T005 — Tipos de resultado da consulta."""

from __future__ import annotations

from investimentos.application.usecases.get_quote import (
    QuoteLookup,
    QuoteOrigin,
    QuoteResolution,
)
from investimentos.domain.model.ticker import Ticker
from tests.conftest import build_quote


def test_resolucao_com_cotacao_do_cache() -> None:
    r = QuoteResolution(Ticker("PETR4"), build_quote(), QuoteOrigin.CACHE)
    assert r.found is True
    assert r.cached is True


def test_resolucao_com_cotacao_da_fonte() -> None:
    r = QuoteResolution(Ticker("PETR4"), build_quote(), QuoteOrigin.SOURCE)
    assert r.found is True
    assert r.cached is False


def test_resolucao_sem_cotacao() -> None:
    r = QuoteResolution(Ticker("ZZZZ9"))
    assert r.found is False
    assert r.cached is False


def test_lookup_preserva_a_ordem_das_resolucoes() -> None:
    """FR-016 — a ordem é responsabilidade nossa, não da fonte."""
    codigos = ["VALE3", "PETR4", "ITSA4"]
    lookup = QuoteLookup(tuple(QuoteResolution(Ticker(c)) for c in codigos))
    assert [r.ticker.value for r in lookup.resolutions] == codigos


def test_lookup_separa_encontrados_de_nao_encontrados() -> None:
    lookup = QuoteLookup(
        (
            QuoteResolution(Ticker("PETR4"), build_quote("PETR4"), QuoteOrigin.CACHE),
            QuoteResolution(Ticker("ZZZZ9")),
            QuoteResolution(Ticker("VALE3"), build_quote("VALE3"), QuoteOrigin.SOURCE),
        )
    )
    assert [r.ticker.value for r in lookup.found] == ["PETR4", "VALE3"]
    assert [r.ticker.value for r in lookup.not_found] == ["ZZZZ9"]


def test_lookup_conta_as_origens() -> None:
    """Alimenta o log do Artigo IX: quantos ativos a requisição poupou de cota."""
    lookup = QuoteLookup(
        (
            QuoteResolution(Ticker("PETR4"), build_quote("PETR4"), QuoteOrigin.CACHE),
            QuoteResolution(Ticker("ITSA4"), build_quote("ITSA4"), QuoteOrigin.CACHE),
            QuoteResolution(Ticker("VALE3"), build_quote("VALE3"), QuoteOrigin.SOURCE),
            QuoteResolution(Ticker("ZZZZ9")),
        )
    )
    assert lookup.from_cache_count == 2
    assert lookup.from_source_count == 1
