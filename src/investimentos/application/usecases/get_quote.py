"""Caso de uso: obter a cotação atual de um ativo."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from investimentos.application.ports.quote_cache import QuoteCachePort
from investimentos.application.ports.quote_provider import QuoteProviderPort
from investimentos.domain.model.quote import Quote
from investimentos.domain.model.ticker import Ticker

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class QuoteResult:
    """Cotação mais o metadado de origem.

    O ``cached`` não pertence ao domínio — a cotação é a mesma tendo vindo do
    cache ou da fonte. Ele existe para tornar o RF-05 observável de fora e
    testável sem inspecionar o Redis (registrado no Complexity Tracking).
    """

    quote: Quote
    cached: bool


class GetQuoteUseCase:
    """Orquestra cache e fonte externa para entregar a cotação de um ativo.

    DIP (Artigo III): recebe as duas portas pelo construtor. Não importa nada
    de ``adapters/``, não sabe que existe Redis nem BRAPI, e não instancia
    nada — quem monta é o composition root.

    Note a ausência de ``try/except`` de infraestrutura: a porta de cache
    promete não explodir (ver ``QuoteCachePort``), então o fluxo aqui é a regra
    de negócio pura, sem defesa contra falha de rede.
    """

    def __init__(self, provider: QuoteProviderPort, cache: QuoteCachePort) -> None:
        self._provider = provider
        self._cache = cache

    async def execute(self, ticker: Ticker) -> QuoteResult:
        cached = await self._cache.get(ticker)
        if cached is not None:
            logger.debug("Cotação de %s servida do cache", ticker)
            return QuoteResult(quote=cached, cached=True)

        quote = await self._provider.fetch(ticker)
        await self._cache.set(ticker, quote)
        return QuoteResult(quote=quote, cached=False)
