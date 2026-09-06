"""Tradução de exceção de domínio para status HTTP (Artigo VIII).

Este é o único lugar do sistema que conhece esse mapeamento. O domínio não sabe
o que é HTTP; o adapter de entrada sabe, e é aqui que a fronteira é atravessada.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from investimentos.domain.exceptions import (
    DomainError,
    InvalidTickerError,
    QuoteNotFoundError,
    QuoteProviderAuthError,
    QuoteProviderContractError,
    QuoteProviderError,
    QuoteProviderRateLimitedError,
    QuoteProviderTimeoutError,
    TooManyTickersError,
)

logger = logging.getLogger(__name__)

PROBLEM_CONTENT_TYPE = "application/problem+json"
_ERROR_BASE = "https://projeto-investimentos/errors"

# exceção -> (status, slug do type, title)
_ERROR_MAP: dict[type[DomainError], tuple[int, str, str]] = {
    InvalidTickerError: (400, "invalid-ticker", "Código de ativo inválido"),
    TooManyTickersError: (400, "too-many-tickers", "Ativos demais na requisição"),
    QuoteNotFoundError: (404, "quote-not-found", "Cotação não encontrada"),
    QuoteProviderAuthError: (502, "provider-auth", "Falha de autenticação na fonte de dados"),
    QuoteProviderRateLimitedError: (503, "provider-rate-limited", "Fonte de dados indisponível"),
    QuoteProviderTimeoutError: (504, "provider-timeout", "Tempo limite excedido na fonte de dados"),
    QuoteProviderContractError: (502, "provider-contract", "Resposta inesperada da fonte de dados"),
    QuoteProviderError: (502, "provider-error", "Falha na fonte de dados"),
}


def _problem(
    request: Request,
    status: int,
    slug: str,
    title: str,
    detail: str | None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type=PROBLEM_CONTENT_TYPE,
        headers=headers,
        content={
            "type": f"{_ERROR_BASE}/{slug}",
            "title": title,
            "status": status,
            "detail": detail,
            "instance": request.url.path,
        },
    )


def _resolve(exc: DomainError) -> tuple[int, str, str]:
    """Escolhe o mapeamento mais específico disponível para a exceção."""
    for exc_type in type(exc).__mro__:
        if exc_type in _ERROR_MAP:
            return _ERROR_MAP[exc_type]
    return 500, "internal-error", "Erro interno"


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain_error(request: Request, exc: DomainError) -> JSONResponse:
        status, slug, title = _resolve(exc)

        # ADR-013: o tempo de espera da fonte é repassado a quem chamou, em vez
        # de virar uma nova tentativa silenciosa que prenderia a conexão.
        headers: dict[str, str] | None = None
        if isinstance(exc, QuoteProviderRateLimitedError) and exc.retry_after is not None:
            headers = {"Retry-After": str(exc.retry_after)}

        if status >= 500:
            logger.error("%s em %s: %s", type(exc).__name__, request.url.path, exc.message)
        else:
            logger.info("%s em %s", type(exc).__name__, request.url.path)
        return _problem(request, status, slug, title, exc.message, headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _problem(
            request,
            400,
            "invalid-request",
            "Requisição inválida",
            "Um ou mais parâmetros da requisição não são válidos.",
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Artigo VIII: nada de stack trace na resposta. O detalhe vai só para o log.
        logger.exception("Erro não tratado em %s", request.url.path)
        return _problem(
            request,
            500,
            "internal-error",
            "Erro interno",
            "Ocorreu um erro inesperado ao processar a requisição.",
        )
