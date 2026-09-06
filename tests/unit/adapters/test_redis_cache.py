"""T019, T020 — Cache em Redis, lendo e gravando em lote (ADR-011)."""

from __future__ import annotations

import pytest
from redis.exceptions import RedisError

from investimentos.adapters.outbound.cache import serializer
from investimentos.adapters.outbound.cache.redis_cache import RedisQuoteCache
from investimentos.domain.model.ticker import Ticker
from tests.conftest import build_quote

PETR4, ITSA4, VALE3 = Ticker("PETR4"), Ticker("ITSA4"), Ticker("VALE3")


class _FakePipeline:
    """Pipeline de mentira que enfileira get/ttl/set e executa em ordem."""

    def __init__(self, redis: FakeRedis) -> None:
        self._redis = redis
        self._ops: list[tuple[str, tuple[object, ...]]] = []

    async def __aenter__(self) -> _FakePipeline:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    def get(self, key: str) -> None:
        self._ops.append(("get", (key,)))

    def ttl(self, key: str) -> None:
        self._ops.append(("ttl", (key,)))

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._ops.append(("set", (key, value, ex or 0)))

    async def execute(self) -> list[object]:
        self._redis.execucoes += 1
        saida: list[object] = []
        for nome, args in self._ops:
            if nome == "get":
                saida.append(self._redis.store.get(args[0]))
            elif nome == "ttl":
                saida.append(self._redis.ttls.get(args[0], -2))
            else:
                key, value, ttl = args
                self._redis.store[key] = value  # type: ignore[index]
                self._redis.ttls[key] = ttl  # type: ignore[index]
                self._redis.gravacoes.append((key, ttl))  # type: ignore[arg-type]
                saida.append(True)
        self._ops.clear()
        return saida


class FakeRedis:
    """Redis de mentira, com o mínimo que o adapter usa."""

    def __init__(self, quebrado: bool = False) -> None:
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self.gravacoes: list[tuple[str, int]] = []
        self.execucoes = 0
        self._quebrado = quebrado

    def pipeline(self, transaction: bool = True) -> _FakePipeline:
        if self._quebrado:
            raise RedisError("cache fora do ar")
        return _FakePipeline(self)

    async def ping(self) -> bool:
        if self._quebrado:
            raise RedisError("cache fora do ar")
        return True


def _semear(redis: FakeRedis, codigo: str, ttl: int = 60) -> None:
    redis.store[f"quote:v1:{codigo}"] = serializer.dumps(build_quote(codigo))
    redis.ttls[f"quote:v1:{codigo}"] = ttl


async def test_get_many_usa_uma_ida_so() -> None:
    """ADR-011 e ADR-018 — valor e validade viajam no mesmo pipeline."""
    redis = FakeRedis()
    _semear(redis, "PETR4")
    _semear(redis, "ITSA4")
    cache = RedisQuoteCache(redis, ttl_seconds=60)  # type: ignore[arg-type]

    encontrados = await cache.get_many([PETR4, ITSA4, VALE3])

    assert redis.execucoes == 1, "valor e TTL têm que vir na mesma ida ao Redis"
    assert set(encontrados) == {PETR4, ITSA4}


async def test_get_many_traz_o_ttl_restante() -> None:
    """FR-009 — a validade anunciada é a que sobrou, não a configurada."""
    redis = FakeRedis()
    _semear(redis, "PETR4", ttl=15)
    cache = RedisQuoteCache(redis, ttl_seconds=60)  # type: ignore[arg-type]

    entrada = (await cache.get_many([PETR4]))[PETR4]

    assert entrada.ttl_seconds == 15, "veio o TTL configurado em vez do restante"


@pytest.mark.parametrize("bruto", [-1, -2, 0])
async def test_ttl_nao_positivo_vira_ausencia_de_validade(bruto: int) -> None:
    """ADR-018 — -1 é chave sem expiração, -2 é inexistente. Nem um nem outro é max-age."""
    redis = FakeRedis()
    _semear(redis, "PETR4", ttl=bruto)
    cache = RedisQuoteCache(redis)  # type: ignore[arg-type]

    assert (await cache.get_many([PETR4]))[PETR4].ttl_seconds is None


async def test_get_many_devolve_so_os_presentes() -> None:
    redis = FakeRedis()
    _semear(redis, "PETR4")
    cache = RedisQuoteCache(redis)  # type: ignore[arg-type]

    encontrados = await cache.get_many([PETR4, VALE3])

    assert set(encontrados) == {PETR4}
    assert encontrados[PETR4].quote.symbol == "PETR4"


async def test_get_many_com_lista_vazia_nao_toca_o_redis() -> None:
    redis = FakeRedis()
    assert await RedisQuoteCache(redis).get_many([]) == {}  # type: ignore[arg-type]
    assert redis.execucoes == 0


async def test_valor_ilegivel_e_tratado_como_ausente() -> None:
    redis = FakeRedis()
    redis.store["quote:v1:PETR4"] = "{lixo que não é json válido"
    redis.ttls["quote:v1:PETR4"] = 60
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
    cache = RedisQuoteCache(redis, ttl_seconds=90)  # type: ignore[arg-type]
    original = build_quote("PETR4")

    await cache.set_many([original])
    entrada = (await cache.get_many([PETR4]))[PETR4]

    assert entrada.quote == original
    assert entrada.ttl_seconds == 90


async def test_falha_na_leitura_devolve_vazio_sem_levantar() -> None:
    """Contrato de robustez da porta (FR-014)."""
    cache = RedisQuoteCache(FakeRedis(quebrado=True))  # type: ignore[arg-type]
    assert await cache.get_many([PETR4]) == {}


async def test_falha_na_gravacao_e_silenciosa() -> None:
    cache = RedisQuoteCache(FakeRedis(quebrado=True))  # type: ignore[arg-type]
    await cache.set_many([build_quote("PETR4")])  # não pode levantar


async def test_ping_falho_devolve_false() -> None:
    assert await RedisQuoteCache(FakeRedis(quebrado=True)).ping() is False  # type: ignore[arg-type]
