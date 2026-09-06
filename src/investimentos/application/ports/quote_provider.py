"""Porta de saída: fonte de cotações."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from investimentos.domain.model.quote import Quote
from investimentos.domain.model.ticker import Ticker


class QuoteProviderPort(Protocol):
    """Contrato de qualquer fonte capaz de informar cotações.

    ADR-002: é um ``Protocol``, não uma ``ABC``. Com tipagem estrutural o
    adapter não precisa importar esta porta nem herdar dela.

    ADR-010: existe **apenas** a operação plural. Consultar um ativo é o caso
    particular de uma lista de um elemento. Manter as duas assinaturas dobraria
    a superfície de teste dos adapters sem que a escolha entre elas importasse
    — ISP do Artigo III e simplicidade do VII.
    """

    async def fetch_many(self, tickers: Sequence[Ticker]) -> Mapping[Ticker, Quote]:
        """Busca as cotações dos ativos informados, em uma única chamada.

        Devolve **apenas os encontrados**. A ausência de um ativo no mapa
        significa que a fonte não o conhece — o que entrega a informação do
        FR-011 sem inventar uma exceção por item dentro de um lote.

        Raises:
            QuoteProviderError: falha de comunicação ou de contrato com a fonte.
        """
        ...
