"""T019, T020 — Cache em Redis, lendo e gravando em lote (ADR-011)."""

from __future__ import annotations

from redis.exceptions import RedisError

from investimentos.adapters.outbound.cache import serializer
from investimentos.adapters.outbound.cache.redis_cache import RedisQuoteCache
from investimentos.domain.model.ticker import Ticker
from tests.conftest import build_quote

PETR4, ITSA4, VALE3 = Ticker("PETR4"), Ticker("ITSA4"), Ticker("VALE3")


class _FakePipeline:
    def __init__(self, store: dict[str, str], gravacoes: list[tuple[str, int]]) -> None:
        self._store = store
        self._gravacoes = gravacoes
        self._pendentes: list[tuple[str, str, int]] = []

    async def __aenter__(self) -> _FakePipeline:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._pendentes.append((key, value, ex or 0))

    async def execute(self) -> None:
        for key, value, ttl in self._pendentes:
            self._store[key] = value
            self._gravacoes.append((key, ttl))
        self._pendentes.clear()


class FakeRedis:
    """Redis de mentira, com o mínimo que o adapter usa."""

    def __init__(self, quebrado: bool = False) -> None:
        self.store: dict[str, str] = {}
        self.mget_calls: list[list[str]] = []
        self.gravacoes: list[tuple[str, int]] = []
        self._quebrado = quebrado

    async def mget(self, keys: list[str]) -> list[str | None]:
        if self._quebrado:
            raise RedisError("cache fora do ar")
        self.mget_calls.append(list(keys))
        return [self.store.get(k) for k in keys]

    def pipeline(self, transaction: bool = True) -> _FakePipeline:
        if self._quebrado:
            raise RedisError("cache fora do ar")
        return _FakePipeline(self.store, self.gravacoes)

    async def ping(self) -> bool:
        if self._quebrado:
            raise RedisError("cache fora do ar")
        return True


async def test_get_many_usa_uma_leitura_so() -> None:
    """ADR-011 — consultar uma vez por ativo trocaria um gargalo por outro."""
    redis = FakeRedis()
    redis.store["quote:v1:PETR4"] = serializer.dumps(build_quote("PETR4"))
    redis.store["quote:v1:ITSA4"] = serializer.dumps(build_quote("ITSA4"))
    cache = RedisQuoteCache(redis, ttl_seconds=60)  # type: ignore[arg-type]

    encontrados = await cache.get_many([PETR4, ITSA4, VALE3])

    assert len(redis.mget_calls) == 1
    assert redis.mget_calls[0] == ["quote:v1:PETR4", "quote:v1:ITSA4", "quote:v1:VALE3"]
    assert set(encontrados) == {PETR4, ITSA4}


async def test_get_many_devolve_so_os_presentes() -> None:
    redis = FakeRedis()
    redis.store["quote:v1:PETR4"] = serializer.dumps(build_quote("PETR4"))
    cache = RedisQuoteCache(redis)  # type: ignore[arg-type]

    encontrados = await cache.get_many([PETR4, VALE3])

    assert set(encontrados) == {PETR4}
    assert encontrados[PETR4].symbol == "PETR4"


async def test_get_many_com_lista_vazia_nao_toca_o_redis() -> None:
    redis = FakeRedis()
    assert await RedisQuoteCache(redis).get_many([]) == {}  # type: ignore[arg-type]
    assert redis.mget_calls == []


async def test_valor_ilegivel_e_tratado_como_ausente() -> None:
    redis = FakeRedis()
    redis.store["quote:v1:PETR4"] = "{lixo que não é json válido"
    cache = RedisQuoteCache(redis)  # type: ignore[arg-type]

    assert await cache.get_many([PETR4]) == {}


async def test_set_many_grava_cada_um_com_ttl_proprio() -> None:
    """FR-008 — validade por ativo, independente."""
    redis = FakeRedis()
    cache = RedisQuoteCache(redis, ttl_seconds=90)  # type: ignore[arg-type]

    await cache.set_many([build_quote("PETR4"), build_quote("ITSA4")])

    assert redis.gravacoes == [("quote:v1:PETR4", 90), ("quote:v1:ITSA4", 90)]


async def test_set_many_vazio_nao_toca_o_redis() -> None:
    redis = FakeRedis()
    await RedisQuoteCache(redis).set_many([])  # type: ignore[arg-type]
    assert redis.gravacoes == []


async def test_ida_e_volta_preserva_a_cotacao() -> None:
    redis = FakeRedis()
    cache = RedisQuoteCache(redis)  # type: ignore[arg-type]
    original = build_quote("PETR4")

    await cache.set_many([original])
    recuperada = (await cache.get_many([PETR4]))[PETR4]

    assert recuperada == original


async def test_falha_na_leitura_devolve_vazio_sem_levantar() -> None:
    """Contrato de robustez da porta (FR-014)."""
    cache = RedisQuoteCache(FakeRedis(quebrado=True))  # type: ignore[arg-type]
    assert await cache.get_many([PETR4]) == {}


async def test_falha_na_gravacao_e_silenciosa() -> None:
    cache = RedisQuoteCache(FakeRedis(quebrado=True))  # type: ignore[arg-type]
    await cache.set_many([build_quote("PETR4")])  # não pode levantar


async def test_ping_falho_devolve_false() -> None:
    assert await RedisQuoteCache(FakeRedis(quebrado=True)).ping() is False  # type: ignore[arg-type]
