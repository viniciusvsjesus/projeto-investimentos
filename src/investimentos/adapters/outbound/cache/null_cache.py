"""Implementação nula da porta de cache.

Artigo VII: esta é a segunda implementação real de ``QuoteCachePort``, o que
justifica a abstração em vez de torná-la especulativa. É usada quando
``REDIS_URL`` não está configurada e nos testes que não devem depender de cache.

LSP (Artigo III): comporta-se como um cache legítimo que sempre erra — nunca
levanta exceção, nunca quebra o chamador.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from investimentos.domain.model.quote import Quote
from investimentos.domain.model.ticker import Ticker


class NullQuoteCache:
    """Cache que não guarda nada."""

    async def get_many(self, tickers: Sequence[Ticker]) -> Mapping[Ticker, Quote]:
        return {}

    async def set_many(self, quotes: Iterable[Quote]) -> None:
        return None

    async def ping(self) -> bool:
        return False

    async def close(self) -> None:
        return None
