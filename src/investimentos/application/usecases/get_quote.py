"""Caso de uso: obter a cotação de um ou mais ativos."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum

from investimentos.application.ports.quote_cache import CachedQuote, QuoteCachePort
from investimentos.application.ports.quote_provider import QuoteProviderPort
from investimentos.domain.exceptions import InvalidTickerError, TooManyTickersError
from investimentos.domain.model.quote import Quote
from investimentos.domain.model.ticker import Ticker

logger = logging.getLogger(__name__)


class QuoteOrigin(Enum):
    """De onde a cotação veio nesta requisição."""

    CACHE = "cache"
    SOURCE = "source"


@dataclass(frozen=True, slots=True)
class QuoteResolution:
    """O que aconteceu com um ativo pedido.

    Vive na aplicação, não no domínio (Artigo X): origem e desfecho são
    resultado de uma orquestração, não propriedade de uma cotação. Uma cotação
    servida do cache é a mesma cotação servida da fonte — colocar ``cached``
    dentro de ``Quote`` faria o domínio saber que existe cache.
    """

    ticker: Ticker
    quote: Quote | None = None
    origin: QuoteOrigin | None = None
    valid_for: int | None = None
    """Segundos que esta cotação ainda vale.

    Do cache, é o que o Redis informou de TTL restante. Da fonte, é o TTL cheio
    — acabou de ser gravada. ``None`` quando não há cotação ou quando o cache
    está desligado, o que a borda traduz em ``no-store`` (ADR-018)."""

    @property
    def found(self) -> bool:
        return self.quote is not None

    @property
    def cached(self) -> bool:
        return self.origin is QuoteOrigin.CACHE


@dataclass(frozen=True, slots=True)
class QuoteLookup:
    """A consulta inteira: um resultado por ativo pedido, na ordem pedida."""

    resolutions: tuple[QuoteResolution, ...]

    @property
    def found(self) -> tuple[QuoteResolution, ...]:
        return tuple(r for r in self.resolutions if r.found)

    @property
    def not_found(self) -> tuple[QuoteResolution, ...]:
        return tuple(r for r in self.resolutions if not r.found)

    @property
    def min_valid_for(self) -> int | None:
        """A menor validade entre as cotações resolvidas.

        ADR-019: o ``Cache-Control`` descreve a **resposta inteira**, não cada
        item. Anunciar a maior validade faria um proxy servir uma lista cujo
        primeiro item já venceu. O menor é o único valor que nunca mente.
        """
        validades = [r.valid_for for r in self.resolutions if r.valid_for]
        return min(validades) if validades else None

    @property
    def from_cache_count(self) -> int:
        return sum(1 for r in self.resolutions if r.origin is QuoteOrigin.CACHE)

    @property
    def from_source_count(self) -> int:
        return sum(1 for r in self.resolutions if r.origin is QuoteOrigin.SOURCE)


class GetQuotesUseCase:
    """Resolve as cotações de um ou mais ativos, poupando cota da fonte.

    A regra econômica que dá razão a esta classe: o cache é consultado
    **individualmente para cada ativo**, e a fonte externa recebe **uma única
    chamada**, apenas com os que faltaram. Se todos estiverem em cache, a fonte
    não é chamada nenhuma vez.

    DIP (Artigo III): recebe as duas portas pelo construtor, não conhece Redis
    nem BRAPI e não instancia nada — quem monta é o composition root.

    Note a ausência de ``try/except`` de infraestrutura: a porta de cache
    promete não explodir, então o que está escrito aqui é só a regra.
    """

    def __init__(
        self,
        provider: QuoteProviderPort,
        cache: QuoteCachePort,
        max_tickers: int = 3,
        cache_ttl_seconds: int = 0,
    ) -> None:
        self._provider = provider
        self._cache = cache
        self._max_tickers = max_tickers
        # Validade a anunciar para o que acabou de ser gravado no cache. Zero
        # quando o cache está desligado — aí não há validade a prometer.
        self._cache_ttl = cache_ttl_seconds

    async def execute(self, tickers: Sequence[Ticker]) -> QuoteLookup:
        pedidos = self._normalize(tickers)

        em_cache = await self._cache.get_many(pedidos)
        faltantes = [t for t in pedidos if t not in em_cache]

        da_fonte: dict[Ticker, Quote] = {}
        if faltantes:
            # Uma chamada só, com todos os que faltaram (FR-006).
            da_fonte = dict(await self._provider.fetch_many(faltantes))
            if da_fonte:
                await self._cache.set_many(da_fonte.values())

        lookup = QuoteLookup(
            resolutions=tuple(
                self._resolve(t, em_cache, da_fonte, self._cache_ttl) for t in pedidos
            )
        )

        # Artigo IX: quantos ativos esta requisição poupou de cota.
        logger.info(
            "Consulta de %d ativo(s): %d do cache, %d da fonte, %d não encontrado(s)",
            len(pedidos),
            lookup.from_cache_count,
            lookup.from_source_count,
            len(lookup.not_found),
        )
        return lookup

    def _normalize(self, tickers: Sequence[Ticker]) -> tuple[Ticker, ...]:
        """Remove repetições preservando a ordem pedida (FR-003, FR-016).

        ``dict.fromkeys`` preserva a ordem de inserção desde o Python 3.7, o que
        torna a deduplicação e a ordenação a mesma operação.
        """
        unicos = tuple(dict.fromkeys(tickers))

        if not unicos:
            raise InvalidTickerError("Informe ao menos um código de ativo.")
        if len(unicos) > self._max_tickers:
            raise TooManyTickersError(requested=len(unicos), limit=self._max_tickers)

        return unicos

    @staticmethod
    def _resolve(
        ticker: Ticker,
        em_cache: Mapping[Ticker, CachedQuote],
        da_fonte: Mapping[Ticker, Quote],
        cache_ttl: int,
    ) -> QuoteResolution:
        if ticker in em_cache:
            entrada = em_cache[ticker]
            return QuoteResolution(
                ticker, entrada.quote, QuoteOrigin.CACHE, entrada.ttl_seconds
            )
        if ticker in da_fonte:
            # Acabou de ser gravada: vale o TTL cheio, se houver cache.
            return QuoteResolution(
                ticker, da_fonte[ticker], QuoteOrigin.SOURCE, cache_ttl or None
            )
        return QuoteResolution(ticker)
