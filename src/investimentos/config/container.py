"""Composition root — o único lugar do sistema que instancia adapters.

Artigo II: nem o caso de uso nem a rota sabem qual implementação está em uso.
Trocar Redis por outro cache, ou BRAPI por outra fonte, é editar este arquivo
e mais nada.
"""

from __future__ import annotations

import logging

import httpx
from redis.asyncio import Redis

from investimentos.adapters.outbound.brapi.client import BrapiQuoteProvider
from investimentos.adapters.outbound.cache.null_cache import NullQuoteCache
from investimentos.adapters.outbound.cache.redis_cache import RedisQuoteCache
from investimentos.application.ports.quote_cache import QuoteCachePort
from investimentos.application.ports.quote_provider import QuoteProviderPort
from investimentos.application.usecases.get_quote import GetQuotesUseCase
from investimentos.config.settings import Settings

logger = logging.getLogger(__name__)


class Container:
    """Monta e mantém o grafo de dependências pelo ciclo de vida da aplicação.

    Recursos de rede — cliente HTTP e conexão com o Redis — são criados uma vez
    na subida e fechados no encerramento (ADR-001), não a cada requisição.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._http_client: httpx.AsyncClient | None = None
        self._redis: Redis | None = None
        self._cache: QuoteCachePort | None = None
        self._provider: QuoteProviderPort | None = None
        self._use_case: GetQuotesUseCase | None = None

    async def startup(self) -> None:
        s = self.settings

        self._http_client = httpx.AsyncClient(
            base_url=s.brapi_base_url,
            timeout=httpx.Timeout(s.brapi_timeout_seconds),
            follow_redirects=True,
            headers={"User-Agent": f"{s.app_name}/{s.app_version}"},
        )
        self._provider = BrapiQuoteProvider(
            client=self._http_client,
            quote_path=s.brapi_quote_path,
            token=s.brapi_token_value,
        )

        # A variável é anotada com a PORTA, não com a implementação: é aqui que
        # a substituição do Artigo III (LSP) acontece de fato.
        cache: QuoteCachePort
        if s.cache_enabled and s.redis_url:
            redis = Redis.from_url(s.redis_url, decode_responses=True)
            self._redis = redis
            cache = RedisQuoteCache(redis, ttl_seconds=s.cache_ttl_seconds)
            logger.info("Cache Redis habilitado com TTL de %ss", s.cache_ttl_seconds)
        else:
            cache = NullQuoteCache()
            logger.info("Cache desabilitado: REDIS_URL não configurada")

        self._cache = cache
        self._use_case = GetQuotesUseCase(
            provider=self._provider,
            cache=cache,
            max_tickers=s.max_tickers_per_request,
            # Sem cache não há validade a prometer: zero vira no-store na borda.
            cache_ttl_seconds=s.cache_ttl_seconds if s.cache_enabled else 0,
        )

    async def shutdown(self) -> None:
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:  # encerramento nunca deve derrubar a aplicação
                logger.warning("Falha ao fechar a conexão com o Redis")
            self._redis = None

    @property
    def get_quotes_use_case(self) -> GetQuotesUseCase:
        if self._use_case is None:
            raise RuntimeError("Container não inicializado: chame startup() primeiro.")
        return self._use_case

    @property
    def cache(self) -> QuoteCachePort:
        if self._cache is None:
            raise RuntimeError("Container não inicializado: chame startup() primeiro.")
        return self._cache
