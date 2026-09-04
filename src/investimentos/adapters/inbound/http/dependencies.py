"""Ponte entre o sistema de injeção do FastAPI e o composition root.

Mantém o container como fonte única da montagem (Artigo II): as rotas pedem
colaboradores por tipo, sem saber quem os construiu nem qual é a implementação.
"""

from __future__ import annotations

from fastapi import Request

from investimentos.application.ports.quote_cache import QuoteCachePort
from investimentos.application.usecases.get_quote import GetQuoteUseCase
from investimentos.config.container import Container


def get_container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


def get_quote_use_case(request: Request) -> GetQuoteUseCase:
    return get_container(request).get_quote_use_case


def get_cache(request: Request) -> QuoteCachePort:
    return get_container(request).cache
