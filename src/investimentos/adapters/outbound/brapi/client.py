"""Adapter de saída: cliente HTTP da BRAPI.

Implementa ``QuoteProviderPort`` por tipagem estrutural (ADR-002) — sem herdar
da porta e sem importá-la, mantendo a dependência apontando para dentro.

SRP (Artigo III): este módulo faz HTTP e traduz status em exceção de domínio.
A tradução de payload para ``Quote`` é do ``mapper``.
"""

from __future__ import annotations

import logging
import time

import httpx

from investimentos.adapters.outbound.brapi.mapper import extract_first_item, to_quote
from investimentos.domain.exceptions import (
    QuoteNotFoundError,
    QuoteProviderAuthError,
    QuoteProviderContractError,
    QuoteProviderError,
    QuoteProviderRateLimitedError,
    QuoteProviderTimeoutError,
)
from investimentos.domain.model.quote import Quote
from investimentos.domain.model.ticker import Ticker

logger = logging.getLogger(__name__)

SOURCE_NAME = "brapi"


class BrapiQuoteProvider:
    """Busca cotações na BRAPI."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        quote_path: str = "/api/v2/stocks/quote?symbols={ticker}",
        token: str | None = None,
    ) -> None:
        self._client = client
        self._quote_path = quote_path
        self._token = token

    def _headers(self) -> dict[str, str]:
        """Monta os headers da requisição.

        Artigo V: o token vai no header ``Authorization``, nunca em query
        string — a própria documentação da BRAPI alerta que query string vaza
        para histórico de navegador e log de servidor.
        """
        headers = {"Accept": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def fetch(self, ticker: Ticker) -> Quote:
        url = self._quote_path.format(ticker=ticker.value)
        started = time.perf_counter()

        try:
            response = await self._client.get(url, headers=self._headers())
        except httpx.TimeoutException as exc:
            logger.warning("Timeout ao consultar %s na BRAPI", ticker)
            raise QuoteProviderTimeoutError(
                f"A fonte não respondeu a tempo para o ativo {ticker}."
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("Falha de rede ao consultar %s na BRAPI", ticker)
            raise QuoteProviderError(
                f"Falha de comunicação com a fonte ao consultar {ticker}."
            ) from exc

        elapsed_ms = (time.perf_counter() - started) * 1000
        # Artigo IX / RNF-07: ticker, latência e desfecho. Jamais o token.
        logger.info(
            "BRAPI %s status=%s latencia=%.0fms",
            ticker,
            response.status_code,
            elapsed_ms,
        )

        self._raise_for_status(response, ticker)

        try:
            payload = response.json()
        except ValueError as exc:
            raise QuoteProviderContractError(
                f"A fonte devolveu um corpo que não é JSON para {ticker}."
            ) from exc

        item = extract_first_item(payload)
        if item is None:
            raise QuoteNotFoundError(ticker.value)

        return to_quote(item, ticker)

    @staticmethod
    def _raise_for_status(response: httpx.Response, ticker: Ticker) -> None:
        """Traduz o status da fonte em exceção de domínio.

        Nenhuma mensagem inclui parte alguma da credencial (Artigo V).
        """
        status = response.status_code

        if status < 400:
            return
        if status == 404:
            raise QuoteNotFoundError(ticker.value)
        if status in (401, 403):
            raise QuoteProviderAuthError(
                "A fonte rejeitou a credencial configurada. Verifique o token da BRAPI."
            )
        if status == 429:
            raise QuoteProviderRateLimitedError(
                "A cota de uso da fonte foi esgotada. Tente novamente mais tarde."
            )
        if status >= 500:
            raise QuoteProviderError(f"A fonte respondeu com erro interno ({status}).")

        raise QuoteProviderError(f"A fonte respondeu com status inesperado ({status}).")
