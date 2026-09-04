"""Raiz do serviço (RF-08).

Abrir ``http://localhost:8000`` no navegador devolve um índice em JSON: o que é
o serviço, se está no ar e qual URL usar para consultar uma cotação. Sem tela,
sem botão — só JSON, que é o que uma API deve devolver.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from investimentos.adapters.inbound.http.dependencies import get_container
from investimentos.adapters.inbound.http.schemas import IndexResponse, RotasDisponiveis
from investimentos.config.container import Container

router = APIRouter(tags=["system"])


@router.get(
    "/",
    response_model=IndexResponse,
    operation_id="index",
    summary="Índice do serviço",
)
async def index(
    request: Request,
    container: Container = Depends(get_container),
) -> IndexResponse:
    settings = container.settings
    return IndexResponse(
        servico=settings.app_name,
        versao=settings.app_version,
        status="ok",
        exemplo=str(request.base_url).rstrip("/") + "/cotacao/PETR4",
        rotas=RotasDisponiveis(),
    )
