"""T063 — Endpoint de saúde (RF-07, CA-02.1, CA-02.2)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from investimentos.adapters.inbound.http.app import create_app
from investimentos.adapters.inbound.http.dependencies import get_cache
from tests.conftest import BrokenQuoteCache, InMemoryQuoteCache


def test_saude_ok_com_cache_desligado(client) -> None:
    corpo = client.get("/health").json()
    assert corpo["status"] == "ok"
    assert corpo["dependencies"]["cache"] == "disabled"


def test_saude_ok_com_cache_no_ar(test_settings) -> None:
    """CA-02.1."""
    settings = test_settings.model_copy(update={"redis_url": "redis://localhost:6379/0"})
    app = create_app(settings)
    app.dependency_overrides[get_cache] = InMemoryQuoteCache

    with TestClient(app) as client:
        corpo = client.get("/health").json()

    assert corpo["status"] == "ok"
    assert corpo["dependencies"]["cache"] == "ok"


def test_saude_degradada_com_cache_fora_do_ar(test_settings) -> None:
    """CA-02.2 — degradado, mas ainda 200: o serviço continua atendendo."""
    settings = test_settings.model_copy(update={"redis_url": "redis://localhost:6379/0"})
    app = create_app(settings)
    app.dependency_overrides[get_cache] = BrokenQuoteCache

    with TestClient(app) as client:
        resposta = client.get("/health")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["status"] == "degraded"
    assert corpo["dependencies"]["cache"] == "unavailable"
