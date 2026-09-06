"""Rotas de cotação — o adapter de entrada do caso de uso.

    GET /acoes/{ticker}   → um objeto
    GET /acoes?ticker=…   → uma lista

O recurso se chama pelo **dado** que devolve — uma ação —, não pelo
identificador. É o que elimina a redundância de `/ticker?ticker=` e o que o
Artigo XI pede.

Uma raiz só, no plural, com o item dentro dela: `/acoes` é a coleção e
`/acoes/ITSA4` é um item daquela coleção (ADR-015).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response

from investimentos.adapters.inbound.http.cache_headers import cache_control
from investimentos.adapters.inbound.http.dependencies import get_quotes_use_case
from investimentos.adapters.inbound.http.schemas import (
    AcaoConsultada,
    CotacaoResponse,
    ProblemDetail,
)
from investimentos.adapters.outbound.brapi.client import SOURCE_NAME
from investimentos.application.usecases.get_quote import GetQuotesUseCase
from investimentos.domain.exceptions import QuoteNotFoundError
from investimentos.domain.model.ticker import Ticker

router = APIRouter(tags=["acoes"])

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
    "/acoes",
    response_model=list[AcaoConsultada],
    operation_id="listAcoes",
    summary="Cotação de vários ativos",
    responses=_ERROS_COMUNS,
)
async def list_acoes(
    response: Response,
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
) -> list[AcaoConsultada]:
    # A validação é do domínio, não do framework: Ticker() levanta
    # InvalidTickerError e o error handler converte em 400 com o corpo
    # padronizado, sem gastar chamada externa. Qualquer código mal formado
    # derruba a requisição inteira — erro de quem chamou não é resultado de busca.
    pedidos = [Ticker(codigo) for codigo in ticker]
    lookup = await use_case.execute(pedidos)

    # ADR-019: vence a menor validade. O cabeçalho descreve a resposta inteira,
    # e ela deixa de servir quando o primeiro item vence.
    response.headers["Cache-Control"] = cache_control(lookup.min_valid_for)

    return AcaoConsultada.from_lookup(lookup, source=SOURCE_NAME)


@router.get(
    "/acoes/{ticker}",
    response_model=CotacaoResponse,
    operation_id="getAcao",
    summary="Cotação de um ativo",
    responses={
        **_ERROS_COMUNS,
        404: {"model": ProblemDetail, "description": "Ativo não encontrado na fonte"},
    },
)
async def get_acao(
    response: Response,
    ticker: str = Path(description=_DESCRICAO_CODIGO, examples=["ITSA4"]),
    use_case: GetQuotesUseCase = Depends(get_quotes_use_case),
) -> CotacaoResponse:
    parsed = Ticker(ticker)
    lookup = await use_case.execute([parsed])
    resolucao = lookup.resolutions[0]

    # ADR-012: num item, "não encontrado" é a ausência do recurso — 404. Na
    # coleção seria um resultado legítimo da busca. A assimetria é deliberada.
    if not resolucao.found:
        raise QuoteNotFoundError(parsed.value)

    response.headers["Cache-Control"] = cache_control(resolucao.valid_for)
    return CotacaoResponse.from_resolution(resolucao, source=SOURCE_NAME)
