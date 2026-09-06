"""Cálculo do cabeçalho de validade da resposta.

Fica na borda porque `Cache-Control` é vocabulário de HTTP, e HTTP só existe
nesta camada (Artigo II).
"""

from __future__ import annotations

NO_STORE = "no-store"


def cache_control(valid_for: int | None) -> str:
    """Traduz a validade restante em um valor de ``Cache-Control``.

    ADR-018: ``valid_for`` é o tempo que a cotação **ainda** vale, medido pelo
    cache — nunca o TTL configurado. Anunciar o TTL cheio para uma cotação que
    já tem 45 segundos de vida faria um proxy servir dado vencido.

    Sem validade — ativo não encontrado, cache desligado ou vencido — a resposta
    é ``no-store`` (FR-012). Prometer zero segundos e prometer nada são coisas
    diferentes: ``max-age=0`` autoriza guardar e revalidar, ``no-store`` não
    autoriza guardar.
    """
    if valid_for is None or valid_for <= 0:
        return NO_STORE
    return f"public, max-age={valid_for}"
