"""T011, T021-T023 — Caso de uso GetQuotes.

Onde vive a regra econômica da Spec 002: o cache é consultado por ativo, e a
fonte recebe uma chamada só, com os que faltaram.
"""

from __future__ import annotations

import pytest

from investimentos.application.usecases.get_quote import GetQuotesUseCase, QuoteOrigin
from investimentos.domain.exceptions import (
    InvalidTickerError,
    QuoteProviderTimeoutError,
    TooManyTickersError,
)
from investimentos.domain.model.ticker import Ticker
from tests.conftest import (
    BrokenQuoteCache,
    InMemoryQuoteCache,
    StubQuoteProvider,
    build_quote,
)

PETR4, ITSA4, VALE3 = Ticker("PETR4"), Ticker("ITSA4"), Ticker("VALE3")


def _use_case(provider, cache, max_tickers: int = 3) -> GetQuotesUseCase:
    return GetQuotesUseCase(provider, cache, max_tickers=max_tickers)


async def test_consulta_tres_ativos_com_uma_chamada() -> None:
    """SC-001 — uma chamada, qualquer que seja a quantidade."""
    provider = StubQuoteProvider([build_quote("PETR4"), build_quote("ITSA4"), build_quote("VALE3")])
    cache = InMemoryQuoteCache()

    lookup = await _use_case(provider, cache).execute([PETR4, ITSA4, VALE3])

    assert len(lookup.resolutions) == 3
    assert all(r.found for r in lookup.resolutions)
    assert provider.call_count == 1


async def test_preserva_a_ordem_pedida() -> None:
    """FR-016."""
    provider = StubQuoteProvider([build_quote("PETR4"), build_quote("ITSA4"), build_quote("VALE3")])

    lookup = await _use_case(provider, InMemoryQuoteCache()).execute([VALE3, PETR4, ITSA4])

    assert [r.ticker.value for r in lookup.resolutions] == ["VALE3", "PETR4", "ITSA4"]


async def test_normaliza_e_deduplica() -> None:
    """FR-003 — o mesmo ativo pedido duas vezes é resolvido e cobrado uma vez."""
    provider = StubQuoteProvider([build_quote("PETR4")])
    cache = InMemoryQuoteCache()

    lookup = await _use_case(provider, cache).execute([Ticker("petr4"), Ticker("PETR4")])

    assert len(lookup.resolutions) == 1
    assert provider.calls == [(PETR4,)]


async def test_consulta_o_cache_por_ativo() -> None:
    """FR-004 — o cache é perguntado sobre cada ativo, não sobre o conjunto."""
    cache = InMemoryQuoteCache()
    provider = StubQuoteProvider([build_quote("PETR4"), build_quote("ITSA4")])

    await _use_case(provider, cache).execute([PETR4, ITSA4])

    assert cache.get_calls == [(PETR4, ITSA4)]


async def test_so_os_faltantes_vao_a_fonte() -> None:
    """SC-004 — o coração da feature."""
    cache = InMemoryQuoteCache()
    await cache.set_many([build_quote("ITSA4")])
    provider = StubQuoteProvider([build_quote("PETR4")])

    lookup = await _use_case(provider, cache).execute([ITSA4, PETR4])

    assert provider.calls == [(PETR4,)], "ITSA4 estava em cache e não podia ir à fonte"
    origens = {r.ticker.value: r.origin for r in lookup.resolutions}
    assert origens["ITSA4"] is QuoteOrigin.CACHE
    assert origens["PETR4"] is QuoteOrigin.SOURCE


async def test_tudo_em_cache_nao_chama_a_fonte() -> None:
    """SC-002 — zero chamadas."""
    cache = InMemoryQuoteCache()
    await cache.set_many([build_quote("PETR4"), build_quote("ITSA4")])
    provider = StubQuoteProvider()

    lookup = await _use_case(provider, cache).execute([PETR4, ITSA4])

    assert provider.call_count == 0
    assert all(r.cached for r in lookup.resolutions)


async def test_grava_no_cache_o_que_veio_da_fonte() -> None:
    """FR-008."""
    cache = InMemoryQuoteCache()
    provider = StubQuoteProvider([build_quote("PETR4"), build_quote("ITSA4")])

    await _use_case(provider, cache).execute([PETR4, ITSA4])

    assert cache.set_calls == [(PETR4, ITSA4)]
    assert set(cache.store) == {PETR4, ITSA4}


async def test_segunda_consulta_vem_toda_do_cache() -> None:
    cache = InMemoryQuoteCache()
    provider = StubQuoteProvider([build_quote("PETR4"), build_quote("ITSA4")])
    use_case = _use_case(provider, cache)

    await use_case.execute([PETR4, ITSA4])
    segunda = await use_case.execute([PETR4, ITSA4])

    assert provider.call_count == 1
    assert all(r.cached for r in segunda.resolutions)


async def test_ativo_desconhecido_pela_fonte_vira_resolucao_sem_cotacao() -> None:
    """FR-011 — não encontrado é resultado, não exceção, dentro de um lote."""
    provider = StubQuoteProvider([build_quote("PETR4")])

    lookup = await _use_case(provider, InMemoryQuoteCache()).execute([PETR4, Ticker("ZZZZ9")])

    por_codigo = {r.ticker.value: r for r in lookup.resolutions}
    assert por_codigo["PETR4"].found is True
    assert por_codigo["ZZZZ9"].found is False
    assert por_codigo["ZZZZ9"].quote is None


async def test_cache_indisponivel_nao_impede_a_consulta() -> None:
    """FR-014 — cache fora do ar degrada desempenho, não disponibilidade."""
    provider = StubQuoteProvider([build_quote("PETR4"), build_quote("ITSA4")])

    lookup = await _use_case(provider, BrokenQuoteCache()).execute([PETR4, ITSA4])

    assert all(r.found for r in lookup.resolutions)
    assert all(not r.cached for r in lookup.resolutions)
    assert provider.calls == [(PETR4, ITSA4)]


async def test_lista_vazia_e_entrada_invalida() -> None:
    with pytest.raises(InvalidTickerError):
        await _use_case(StubQuoteProvider(), InMemoryQuoteCache()).execute([])


async def test_acima_do_limite_e_recusado_sem_chamar_a_fonte() -> None:
    """FR-010, SC-005 — a validação protege a cota."""
    provider = StubQuoteProvider()

    with pytest.raises(TooManyTickersError) as exc:
        await _use_case(provider, InMemoryQuoteCache(), max_tickers=3).execute(
            [PETR4, ITSA4, VALE3, Ticker("BOVA11")]
        )

    assert exc.value.requested == 4
    assert exc.value.limit == 3
    assert provider.call_count == 0


async def test_duplicados_nao_contam_para_o_limite() -> None:
    """Quatro pedidos, três ativos distintos: passa."""
    provider = StubQuoteProvider([build_quote("PETR4"), build_quote("ITSA4"), build_quote("VALE3")])

    lookup = await _use_case(provider, InMemoryQuoteCache(), max_tickers=3).execute(
        [PETR4, ITSA4, VALE3, PETR4]
    )

    assert len(lookup.resolutions) == 3


async def test_falha_da_fonte_propaga_sem_gravar_no_cache() -> None:
    cache = InMemoryQuoteCache()
    provider = StubQuoteProvider(error=QuoteProviderTimeoutError("timeout"))

    with pytest.raises(QuoteProviderTimeoutError):
        await _use_case(provider, cache).execute([PETR4])

    assert cache.set_calls == []
