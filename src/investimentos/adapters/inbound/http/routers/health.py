"""Endpoint de saúde (RF-07, Artigo IX)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from investimentos.adapters.inbound.http.dependencies import get_cache, get_container
from investimentos.adapters.inbound.http.schemas import DependenciesStatus, HealthResponse
from investimentos.application.ports.quote_cache import QuoteCachePort

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, operation_id="health", summary="Saúde")
async def health(
    request: Request,
    cache: QuoteCachePort = Depends(get_cache),
) -> HealthResponse:
    """Reporta o serviço e suas dependências.

    Cache fora do ar deixa o serviço ``degraded``, mas a resposta continua
    ``200``: a consulta de cotação segue funcionando (RF-06, CA-02.2), e
    derrubar o healthcheck faria o orquestrador tirar de rotação um serviço
    que está atendendo.
    """
    settings = get_container(request).settings

    if not settings.cache_enabled:
        return HealthResponse(status="ok", dependencies=DependenciesStatus(cache="disabled"))

    cache_ok = await cache.ping()
    return HealthResponse(
        status="ok" if cache_ok else "degraded",
        dependencies=DependenciesStatus(cache="ok" if cache_ok else "unavailable"),
    )
