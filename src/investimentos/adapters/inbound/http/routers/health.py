"""Endpoint de saúde (Artigo IX)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from investimentos.adapters.inbound.http.dependencies import get_cache, get_container
from investimentos.adapters.inbound.http.schemas import DependenciasSaude, SaudeResponse
from investimentos.application.ports.quote_cache import QuoteCachePort

router = APIRouter(tags=["sistema"])


@router.get("/health", response_model=SaudeResponse, operation_id="health", summary="Saúde")
async def health(
    request: Request,
    cache: QuoteCachePort = Depends(get_cache),
) -> SaudeResponse:
    """Reporta o serviço e suas dependências.

    Cache fora do ar deixa o serviço ``degradado``, mas a resposta continua
    ``200``: a consulta de cotação segue funcionando, e derrubar o healthcheck
    faria o orquestrador tirar de rotação um serviço que está atendendo.
    """
    settings = get_container(request).settings

    if not settings.cache_enabled:
        return SaudeResponse(situacao="ok", dependencias=DependenciasSaude(cache="desligado"))

    cache_ok = await cache.ping()
    return SaudeResponse(
        situacao="ok" if cache_ok else "degradado",
        dependencias=DependenciasSaude(cache="ok" if cache_ok else "indisponivel"),
    )
