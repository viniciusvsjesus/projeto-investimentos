"""T020 — Cálculo do Cache-Control (FR-010, FR-012)."""

from __future__ import annotations

import pytest

from investimentos.adapters.inbound.http.cache_headers import cache_control


@pytest.mark.parametrize("segundos", [1, 12, 42, 60, 3600])
def test_validade_positiva_vira_max_age(segundos: int) -> None:
    assert cache_control(segundos) == f"public, max-age={segundos}"


def test_sem_validade_e_no_store() -> None:
    """FR-012 — não há o que cachear."""
    assert cache_control(None) == "no-store"


@pytest.mark.parametrize("segundos", [0, -1, -2])
def test_validade_nao_positiva_e_no_store(segundos: int) -> None:
    """Os -1 e -2 do Redis nunca podem virar max-age.

    Prometer zero segundos e prometer nada são coisas diferentes: `max-age=0`
    autoriza guardar e revalidar, `no-store` não autoriza guardar.
    """
    assert cache_control(segundos) == "no-store"
