"""Adapter de saída: cliente HTTP da BRAPI.

Implementa ``QuoteProviderPort`` por tipagem estrutural (ADR-002) — sem herdar
da porta e sem importá-la, mantendo a dependência apontando para dentro.

SRP (Artigo III): este módulo faz HTTP e traduz status em exceção de domínio.
A tradução de payload para ``Quote`` é do ``mapper``.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping, Sequence

import httpx

from investimentos.adapters.outbound.brapi.mapper import to_quotes
from investimentos.domain.exceptions import (
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

    async def fetch_many(self, tickers: Sequence[Ticker]) -> Mapping[Ticker, Quote]:
        """Busca todos os ativos em **uma única** chamada (FR-006).

        ADR-009: a fonte aceita vários códigos separados por vírgula. É isso que
        transforma N consultas em uma e preserva a cota.
        """
        if not tickers:
            return {}

        codigos = ",".join(t.value for t in tickers)
        url = self._quote_path.format(ticker=codigos)
        started = time.perf_counter()

        try:
            response = await self._client.get(url, headers=self._headers())
        except httpx.TimeoutException as exc:
            logger.warning("Timeout ao consultar %s na BRAPI", codigos)
            raise QuoteProviderTimeoutError(
                f"A fonte não respondeu a tempo para: {codigos}."
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("Falha de rede ao consultar %s na BRAPI", codigos)
            raise QuoteProviderError(
                f"Falha de comunicação com a fonte ao consultar: {codigos}."
            ) from exc

        elapsed_ms = (time.perf_counter() - started) * 1000
        # Artigo IX: códigos, latência, desfecho e cota restante. Jamais o token.
        logger.info(
            "BRAPI %s status=%s latencia=%.0fms cota_restante=%s",
            codigos,
            response.status_code,
            elapsed_ms,
            response.headers.get("RateLimit-Remaining", "?"),
        )

        self._raise_for_status(response, codigos)

        if response.status_code == 404:
            # Nenhum dos códigos existe. Mapa vazio diz isso sem derrubar o lote
            # nem tentar interpretar um corpo de erro como se fosse cotação.
            return {}

        try:
            payload = response.json()
        except ValueError as exc:
            raise QuoteProviderContractError(
                f"A fonte devolveu um corpo que não é JSON para: {codigos}."
            ) from exc

        return to_quotes(payload, tickers)

    @staticmethod
    def _raise_for_status(response: httpx.Response, codigos: str) -> None:
        """Traduz o status da fonte em exceção de domínio.

        Nenhuma mensagem inclui parte alguma da credencial (Artigo V).

        Note que `404` **não** vira "não encontrado" aqui: num lote, um código
        desconhecido não é motivo para a requisição inteira falhar. A ausência
        do ativo no mapa devolvido é que carrega essa informação (ADR-010).
        """
        status = response.status_code

        if status < 400:
            return
        if status in (401, 403):
            raise QuoteProviderAuthError(
                "A fonte rejeitou a credencial configurada. Verifique o token da BRAPI."
            )
        if status == 429:
            raise QuoteProviderRateLimitedError(
                "A cota de uso da fonte foi esgotada. Tente novamente mais tarde.",
                retry_after=_parse_retry_after(response.headers.get("Retry-After")),
            )
        if status == 404:
            # Tratado por fetch_many, que devolve mapa vazio.
            return
        if status >= 500:
            raise QuoteProviderError(f"A fonte respondeu com erro interno ({status}).")

        raise QuoteProviderError(f"A fonte respondeu com status inesperado ({status}).")


def _parse_retry_after(raw: str | None) -> int | None:
    """Lê o ``Retry-After`` em segundos. Formato de data é ignorado."""
    if raw is None:
        return None
    try:
        return max(0, int(raw.strip()))
    except (ValueError, AttributeError):
        return None
