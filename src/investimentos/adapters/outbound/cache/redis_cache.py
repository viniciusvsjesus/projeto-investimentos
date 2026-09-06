"""Adapter de saída: cache de cotações em Redis."""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Iterable, Mapping, Sequence

from redis.asyncio import Redis
from redis.exceptions import RedisError

from investimentos.adapters.outbound.cache import serializer
from investimentos.domain.model.quote import Quote
from investimentos.domain.model.ticker import Ticker

logger = logging.getLogger(__name__)

# ADR-005: o prefixo carrega versão. As chaves gravadas pela Spec 001 continuam
# válidas — a Spec 002 muda o acesso, não o formato.
_KEY_PREFIX = "quote:v1"


class RedisQuoteCache:
    """Guarda cotações no Redis com TTL, lendo e gravando em lote.

    ADR-011: uma ida na leitura (``MGET``) e uma na gravação (pipeline),
    independente de quantos ativos. Consultar uma vez por ativo transformaria a
    economia de chamadas externas em várias idas ao cache.

    Cumpre o contrato de robustez da ``QuoteCachePort``: **nenhuma** falha de
    infraestrutura escapa daqui. Redis fora do ar devolve resultado vazio, e a
    API continua servindo cotações (FR-014).
    """

    def __init__(self, redis: Redis, ttl_seconds: int = 60) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    @staticmethod
    def _key(ticker: Ticker) -> str:
        return f"{_KEY_PREFIX}:{ticker.value}"

    async def get_many(self, tickers: Sequence[Ticker]) -> Mapping[Ticker, Quote]:
        if not tickers:
            return {}

        try:
            brutos = await self._redis.mget([self._key(t) for t in tickers])
        except RedisError:
            logger.warning("Cache indisponível na leitura; seguindo para a fonte")
            return {}

        encontrados: dict[Ticker, Quote] = {}
        for ticker, bruto in zip(tickers, brutos, strict=False):
            if bruto is None:
                continue
            if isinstance(bruto, bytes):
                bruto = bruto.decode("utf-8")
            try:
                encontrados[ticker] = serializer.loads(bruto)
            except Exception:
                # Dado corrompido ou de formato antigo: trata como ausente e
                # deixa a próxima gravação sobrescrever.
                logger.warning("Valor em cache ilegível para %s; tratando como ausente", ticker)

        return encontrados

    async def set_many(self, quotes: Iterable[Quote]) -> None:
        lista = list(quotes)
        if not lista:
            return

        try:
            async with self._redis.pipeline(transaction=False) as pipe:
                for quote in lista:
                    pipe.set(self._key(quote.ticker), serializer.dumps(quote), ex=self._ttl)
                await pipe.execute()
        except RedisError:
            logger.warning("Cache indisponível na gravação de %d cotação(ões)", len(lista))

    async def ping(self) -> bool:
        try:
            return bool(await self._redis.ping())
        except RedisError:
            return False

    async def close(self) -> None:
        with contextlib.suppress(RedisError, AttributeError):
            await self._redis.aclose()
