"""Rota de cotação — o adapter de entrada do caso de uso.

    GET /cotacao/{ticker}

Devolve JSON puro. Abrir no navegador já mostra o resultado; não há tela
intermediária nem botão para clicar.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path

from investimentos.adapters.inbound.http.dependencies import get_quote_use_case
from investimentos.adapters.inbound.http.schemas import ProblemDetail, QuoteResponse
from investimentos.adapters.outbound.brapi.client import SOURCE_NAME
from investimentos.application.usecases.get_quote import GetQuoteUseCase
from investimentos.domain.model.ticker import Ticker

router = APIRouter(tags=["cotacao"])

_ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
    400: {"model": ProblemDetail, "description": "Código de ativo com formato inválido"},
    404: {"model": ProblemDetail, "description": "Ativo não encontrado na fonte"},
    502: {"model": ProblemDetail, "description": "Falha de comunicação ou contrato com a fonte"},
    503: {"model": ProblemDetail, "description": "Cota da fonte externa esgotada"},
    504: {"model": ProblemDetail, "description": "Fonte externa excedeu o tempo limite"},
}


@router.get(
    "/cotacao/{ticker}",
    response_model=QuoteResponse,
    operation_id="getCotacao",
    summary="Cotação atual de um ativo",
    responses=_ERROR_RESPONSES,
)
async def get_cotacao(
    ticker: str = Path(
        description=(
            "Código de negociação na B3. Aceita minúsculas (normalizado para maiúsculas). "
            "Padrão: quatro letras, um ou dois dígitos, 'F' opcional."
        ),
        examples=["PETR4"],
    ),
    use_case: GetQuoteUseCase = Depends(get_quote_use_case),
) -> QuoteResponse:
    # A validação é do domínio, não do framework: Ticker() levanta
    # InvalidTickerError, que o error handler converte em 400 com o corpo
    # padronizado (CA-01.2). Deixar o FastAPI validar por regex devolveria 422
    # e um corpo fora do nosso contrato de erro.
    parsed = Ticker(ticker)
    result = await use_case.execute(parsed)
    return QuoteResponse.from_result(result, source=SOURCE_NAME)
