"""T022–T025 — Caso de uso GetQuote (RF-01, RF-05, RF-06)."""

from __future__ import annotations

import pytest

from investimentos.application.usecases.get_quote import GetQuoteUseCase
from investimentos.domain.exceptions import QuoteNotFoundError, QuoteProviderTimeoutError
from investimentos.domain.model.ticker import Ticker
from tests.conftest import BrokenQuoteCache, InMemoryQuoteCache, StubQuoteProvider

TICKER = Ticker("PETR4")


async def test_cache_miss_consulta_a_fonte_e_grava(sample_quote) -> None:
    """RF-05 — primeira consulta vai à fonte e popula o cache."""
    provider = StubQuoteProvider(quote=sample_quote)
    cache = InMemoryQuoteCache()

    resultado = await GetQuoteUseCase(provider, cache).execute(TICKER)

    assert resultado.quote == sample_quote
    assert resultado.cached is False
    assert provider.calls == 1
    assert cache.set_calls == 1


async def test_cache_hit_nao_chama_a_fonte(sample_quote) -> None:
    """RF-05 / CA-01.5 — o ponto inteiro do cache é este."""
    provider = StubQuoteProvider(quote=sample_quote)
    cache = InMemoryQuoteCache()
    await cache.set(TICKER, sample_quote)

    resultado = await GetQuoteUseCase(provider, cache).execute(TICKER)

    assert resultado.cached is True
    assert provider.calls == 0


async def test_segunda_chamada_vem_do_cache(sample_quote) -> None:
    provider = StubQuoteProvider(quote=sample_quote)
    use_case = GetQuoteUseCase(provider, InMemoryQuoteCache())

    primeira = await use_case.execute(TICKER)
    segunda = await use_case.execute(TICKER)

    assert primeira.cached is False
    assert segunda.cached is True
    assert provider.calls == 1


async def test_cache_indisponivel_nao_impede_a_resposta(sample_quote) -> None:
    """RF-06 / CA-02.2 — cache fora do ar degrada desempenho, não disponibilidade."""
    provider = StubQuoteProvider(quote=sample_quote)

    resultado = await GetQuoteUseCase(provider, BrokenQuoteCache()).execute(TICKER)

    assert resultado.quote == sample_quote
    assert resultado.cached is False
    assert provider.calls == 1


async def test_falha_ao_gravar_no_cache_nao_derruba_a_resposta(sample_quote) -> None:
    """RF-06 — a porta promete não explodir, então o caso de uso não se defende."""
    provider = StubQuoteProvider(quote=sample_quote)
    resultado = await GetQuoteUseCase(provider, BrokenQuoteCache()).execute(TICKER)
    assert resultado.quote == sample_quote


async def test_propaga_ativo_nao_encontrado() -> None:
    provider = StubQuoteProvider(error=QuoteNotFoundError("ZZZZ9"))
    with pytest.raises(QuoteNotFoundError):
        await GetQuoteUseCase(provider, InMemoryQuoteCache()).execute(TICKER)


async def test_propaga_falha_da_fonte_sem_gravar_no_cache() -> None:
    provider = StubQuoteProvider(error=QuoteProviderTimeoutError("timeout"))
    cache = InMemoryQuoteCache()

    with pytest.raises(QuoteProviderTimeoutError):
        await GetQuoteUseCase(provider, cache).execute(TICKER)

    assert cache.set_calls == 0
