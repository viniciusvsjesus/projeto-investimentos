"""Factory da aplicação FastAPI.

Todo o FastAPI do projeto vive sob ``adapters/inbound/http/``. Nada em
``domain/`` ou ``application/`` importa este módulo — é o Artigo II na prática.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from investimentos.adapters.inbound.http.error_handlers import register_error_handlers
from investimentos.adapters.inbound.http.routers import health, root, ticker
from investimentos.config.container import Container
from investimentos.config.logging import configure_logging
from investimentos.config.settings import Settings, get_settings

_DESCRIPTION = """
API que expõe cotações de ativos da B3 em um contrato próprio e estável,
isolando os consumidores da fonte externa de dados.

Uso:

- `GET /ticker/{ticker}` — um ativo, devolve um objeto.
  Exemplo: [`/ticker/PETR4`](/ticker/PETR4)
- `GET /ticker?ticker=A&ticker=B` — vários, devolve uma lista.
  Exemplo: [`/ticker?ticker=ITSA4&ticker=PETR4`](/ticker?ticker=ITSA4&ticker=PETR4)

Cada ativo é procurado no cache individualmente; só os ausentes vão à fonte
externa, e numa única chamada.

Construída por **SDD** (desenvolvimento guiado por especificação). Os artefatos
que originaram cada linha deste serviço estão em `specs/001-cotacao-ticker/`,
e as regras que governam o código estão em `.specify/memory/constitution.md`.
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    """Monta a aplicação. Recebe ``settings`` para que o teste injete as suas."""
    resolved = settings or get_settings()

    configure_logging(
        level=resolved.log_level,
        json_output=resolved.app_env != "development",
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # ADR-001: cliente HTTP e conexão com o Redis são criados uma vez na
        # subida e reaproveitados, não abertos a cada requisição.
        container = Container(resolved)
        await container.startup()
        app.state.container = container
        try:
            yield
        finally:
            await container.shutdown()

    app = FastAPI(
        title=resolved.app_name,
        version=resolved.app_version,
        description=_DESCRIPTION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    register_error_handlers(app)
    app.include_router(root.router)
    app.include_router(health.router)
    app.include_router(ticker.router)

    return app
