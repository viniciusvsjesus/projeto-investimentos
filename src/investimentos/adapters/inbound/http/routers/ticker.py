"""Rotas de cotação — o adapter de entrada do caso de uso.

    GET /ticker/{ticker}   → um objeto
    GET /ticker?ticker=…   → uma lista

As duas devolvem JSON puro. Abrir no navegador já mostra o resultado.

Artigo XI: item devolve objeto, coleção devolve lista — e continua devolvendo
lista quando o resultado tem um elemento só. O consumidor nunca precisa checar
o tipo antes de ler.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from investimentos.adapters.inbound.http.dependencies import get_quotes_use_case
from investimentos.adapters.inbound.http.schemas import (
    ProblemDetail,
    QuoteResponse,
    TickerLookupItem,
)
from investimentos.adapters.outbound.brapi.client import SOURCE_NAME
from investimentos.application.usecases.get_quote import GetQuotesUseCase
from investimentos.domain.exceptions import QuoteNotFoundError
from investimentos.domain.model.ticker import Ticker

router = APIRouter(tags=["ticker"])

_ERROS_COMUNS: dict[int | str, dict[str, object]] = {
    400: {"model": ProblemDetail, "description": "Código com formato inválido"},
    502: {"model": ProblemDetail, "description": "Falha de comunicação ou contrato com a fonte"},
    503: {"model": ProblemDetail, "description": "Cota da fonte externa esgotada"},
    504: {"model": ProblemDetail, "description": "Fonte externa excedeu o tempo limite"},
}

_DESCRICAO_CODIGO = (
    "Código de negociação na B3. Aceita minúsculas (normalizado para maiúsculas). "
    "Padrão: quatro caracteres começando por letra, mais um ou dois dígitos."
)


@router.get(
    "/ticker",
    response_model=list[TickerLookupItem],
    operation_id="listTickers",
    summary="Cotação de vários ativos",
    responses=_ERROS_COMUNS,
)
async def list_tickers(
    ticker: Annotated[
        list[str],
        Query(
            description=(
                "Repita o parâmetro para consultar vários: "
                "`?ticker=ITSA4&ticker=PETR4`. Repetições do mesmo código contam "
                "uma vez, e a ordem da resposta acompanha a do pedido."
            ),
            examples=[["ITSA4", "PETR4"]],
        ),
    ],
    use_case: GetQuotesUseCase = Depends(get_quotes_use_case),
) -> list[TickerLookupItem]:
    # A validação é do domínio, não do framework: Ticker() levanta
    # InvalidTickerError e o error handler converte em 400 com o corpo
    # padronizado, sem gastar chamada externa (FR-002, SC-005). Qualquer código
    # mal formado derruba a requisição inteira — erro de quem chamou não é
    # resultado de busca (FR-011).
    pedidos = [Ticker(codigo) for codigo in ticker]
    lookup = await use_case.execute(pedidos)
    return TickerLookupItem.from_lookup(lookup, source=SOURCE_NAME)


@router.get(
    "/ticker/{ticker}",
    response_model=QuoteResponse,
    operation_id="getTicker",
    summary="Cotação de um ativo",
    responses={
        **_ERROS_COMUNS,
        404: {"model": ProblemDetail, "description": "Ativo não encontrado na fonte"},
    },
)
async def get_ticker(
    ticker: str = Path(description=_DESCRICAO_CODIGO, examples=["PETR4"]),
    use_case: GetQuotesUseCase = Depends(get_quotes_use_case),
) -> QuoteResponse:
    parsed = Ticker(ticker)
    lookup = await use_case.execute([parsed])
    resolucao = lookup.resolutions[0]

    # ADR-012: num item, "não encontrado" é a ausência do recurso — 404. Na
    # coleção seria um resultado legítimo da busca. A assimetria é deliberada.
    if not resolucao.found:
        raise QuoteNotFoundError(parsed.value)

    return QuoteResponse.from_resolution(resolucao, source=SOURCE_NAME)
