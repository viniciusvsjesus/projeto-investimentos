"""Raiz do serviço.

Abrir ``http://localhost:8000`` no navegador devolve um índice em JSON: o que é
o serviço, se está no ar e qual URL usar. Sem tela, sem botão.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from investimentos.adapters.inbound.http.dependencies import get_container
from investimentos.adapters.inbound.http.schemas import IndiceResponse, RotasDisponiveis
from investimentos.config.container import Container

router = APIRouter(tags=["sistema"])


@router.get(
    "/",
    response_model=IndiceResponse,
    operation_id="index",
    summary="Índice do serviço",
)
async def index(
    request: Request,
    container: Container = Depends(get_container),
) -> IndiceResponse:
    settings = container.settings
    base = str(request.base_url).rstrip("/")
    return IndiceResponse(
        servico=settings.app_name,
        versao=settings.app_version,
        situacao="ok",
        exemplo=f"{base}/acoes/ITSA4",
        rotas=RotasDisponiveis(),
    )
