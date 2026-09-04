"""Adapter de saída: cache de cotações em Redis."""

from __future__ import annotations

import contextlib
import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from investimentos.adapters.outbound.cache import serializer
from investimentos.domain.model.quote import Quote
from investimentos.domain.model.ticker import Ticker

logger = logging.getLogger(__name__)

# ADR-005: o prefixo carrega versão. Mudar o formato serializado no futuro é
# trocar 'v1' por 'v2' — as chaves antigas expiram sozinhas pelo TTL.
_KEY_PREFIX = "quote:v1"


class RedisQuoteCache:
    """Guarda cotações no Redis com TTL.

    Cumpre o contrato de robustez da ``QuoteCachePort``: **nenhuma** falha de
    infraestrutura escapa daqui. Redis fora do ar vira miss, e a API continua
    servindo cotações (RF-06, CA-02.2).
    """

    def __init__(self, redis: Redis, ttl_seconds: int = 60) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    @staticmethod
    def _key(ticker: Ticker) -> str:
        return f"{_KEY_PREFIX}:{ticker.value}"

    async def get(self, ticker: Ticker) -> Quote | None:
        try:
            raw = await self._redis.get(self._key(ticker))
        except RedisError:
            logger.warning("Cache indisponível na leitura de %s; seguindo para a fonte", ticker)
            return None

        if raw is None:
            return None

        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")

        try:
            return serializer.loads(raw)
        except Exception:
            # Dado corrompido ou de um formato antigo: trata como miss e
            # deixa a próxima gravação sobrescrever.
            logger.warning("Valor em cache ilegível para %s; tratando como miss", ticker)
            return None

    async def set(self, ticker: Ticker, quote: Quote) -> None:
        try:
            await self._redis.set(self._key(ticker), serializer.dumps(quote), ex=self._ttl)
        except RedisError:
            logger.warning("Cache indisponível na gravação de %s", ticker)

    async def ping(self) -> bool:
        try:
            return bool(await self._redis.ping())
        except RedisError:
            return False

    async def close(self) -> None:
        with contextlib.suppress(RedisError, AttributeError):
            await self._redis.aclose()
