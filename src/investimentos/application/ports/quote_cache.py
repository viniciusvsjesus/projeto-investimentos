"""Porta de saída: cache de cotações."""

from __future__ import annotations

from typing import Protocol

from investimentos.domain.model.quote import Quote
from investimentos.domain.model.ticker import Ticker


class QuoteCachePort(Protocol):
    """Contrato de armazenamento temporário de cotações.

    Contrato de robustez (LSP, Artigo III): **nenhum** método desta porta pode
    levantar exceção por falha de infraestrutura. Cache fora do ar é um `miss`,
    nunca um erro — é o que permite ao caso de uso não ter um único
    ``try/except`` de infraestrutura e atende ao RF-06.
    """

    async def get(self, ticker: Ticker) -> Quote | None:
        """Devolve a cotação em cache, ou ``None`` em miss ou indisponibilidade."""
        ...

    async def set(self, ticker: Ticker, quote: Quote) -> None:
        """Grava a cotação. Falha de gravação é silenciosa por contrato."""
        ...

    async def ping(self) -> bool:
        """Informa se o cache está operacional. Usado pelo ``/health``."""
        ...
