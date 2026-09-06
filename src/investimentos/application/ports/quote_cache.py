"""Porta de saída: cache de cotações."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Protocol

from investimentos.domain.model.quote import Quote
from investimentos.domain.model.ticker import Ticker


class QuoteCachePort(Protocol):
    """Contrato de armazenamento temporário de cotações.

    Contrato de robustez (LSP, Artigo III): **nenhum** método desta porta pode
    levantar exceção por falha de infraestrutura. Cache fora do ar devolve
    resultado vazio, nunca erro — é o que permite ao caso de uso não ter um
    único ``try/except`` de infraestrutura e atende ao FR-014.

    ADR-010 e ADR-011: as operações são em lote. Consultar o cache uma vez por
    ativo transformaria a economia de chamadas externas em várias idas ao
    Redis — trocaria um gargalo por outro.
    """

    async def get_many(self, tickers: Sequence[Ticker]) -> Mapping[Ticker, Quote]:
        """Devolve as cotações em cache. Ausentes simplesmente não vêm no mapa.

        Indisponibilidade do cache devolve mapa vazio: todos viram faltantes.
        """
        ...

    async def set_many(self, quotes: Iterable[Quote]) -> None:
        """Grava as cotações, cada uma com validade própria.

        Falha de gravação é silenciosa por contrato.
        """
        ...

    async def ping(self) -> bool:
        """Informa se o cache está operacional. Usado pelo ``/health``."""
        ...
