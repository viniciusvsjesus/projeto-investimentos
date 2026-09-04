"""Porta de saída: fonte de cotações."""

from __future__ import annotations

from typing import Protocol

from investimentos.domain.model.quote import Quote
from investimentos.domain.model.ticker import Ticker


class QuoteProviderPort(Protocol):
    """Contrato de qualquer fonte capaz de informar a cotação de um ativo.

    ADR-002: é um ``Protocol``, não uma ``ABC``. Com tipagem estrutural o
    adapter não precisa importar esta porta nem herdar dela — ele apenas
    apresenta os métodos certos. A dependência continua apontando para dentro,
    e um dublê de teste vira uma classe qualquer, sem herança.

    ISP (Artigo III): um método só. Dividendos e histórico, quando existirem,
    ganham portas próprias em vez de engordar esta.
    """

    async def fetch(self, ticker: Ticker) -> Quote:
        """Obtém a cotação atual do ativo.

        Raises:
            QuoteNotFoundError: a fonte respondeu, mas não conhece o ativo.
            QuoteProviderError: qualquer falha de comunicação ou de contrato.
        """
        ...
