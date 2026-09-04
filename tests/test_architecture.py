"""T065 — O Artigo II verificado por AST, não por combinado verbal.

A regra da arquitetura hexagonal — dependência apontando sempre para dentro —
costuma ser um acordo que a equipe esquece no terceiro sprint. Aqui ela é um
teste: se alguém importar FastAPI dentro do domínio, o build quebra.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

RAIZ_SRC = Path(__file__).resolve().parents[1] / "src" / "investimentos"

STDLIB = set(sys.stdlib_module_names)
PACOTE = "investimentos"


def _modulos(camada: str) -> list[Path]:
    return sorted((RAIZ_SRC / camada).rglob("*.py"))


def _imports(arquivo: Path) -> list[str]:
    """Todos os módulos importados por um arquivo, em nome absoluto."""
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"), filename=str(arquivo))
    encontrados: list[str] = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            encontrados.extend(alias.name for alias in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module and no.level == 0:
            encontrados.append(no.module)
    return encontrados


def _raiz(modulo: str) -> str:
    return modulo.split(".")[0]


@pytest.mark.parametrize("arquivo", _modulos("domain"), ids=lambda p: p.name)
def test_dominio_nao_importa_camadas_externas(arquivo: Path) -> None:
    """Artigo II: o núcleo não conhece aplicação nem adapters."""
    for modulo in _imports(arquivo):
        assert not modulo.startswith(f"{PACOTE}.application"), f"{arquivo.name} importa application"
        assert not modulo.startswith(f"{PACOTE}.adapters"), f"{arquivo.name} importa adapters"
        assert not modulo.startswith(f"{PACOTE}.config"), f"{arquivo.name} importa config"


@pytest.mark.parametrize("arquivo", _modulos("domain"), ids=lambda p: p.name)
def test_dominio_usa_apenas_a_biblioteca_padrao(arquivo: Path) -> None:
    """RNF-05: se o domínio precisa de Pydantic para existir, o desenho está errado."""
    for modulo in _imports(arquivo):
        raiz = _raiz(modulo)
        if raiz == PACOTE or raiz == "__future__":
            continue
        assert raiz in STDLIB, f"{arquivo.name} importa biblioteca de terceiros: {modulo}"


@pytest.mark.parametrize("arquivo", _modulos("application"), ids=lambda p: p.name)
def test_aplicacao_nao_importa_adapters(arquivo: Path) -> None:
    """Artigo II / DIP: os casos de uso dependem das portas, não das implementações."""
    for modulo in _imports(arquivo):
        assert not modulo.startswith(f"{PACOTE}.adapters"), f"{arquivo.name} importa adapters"
        assert not modulo.startswith(f"{PACOTE}.config"), f"{arquivo.name} importa config"


@pytest.mark.parametrize("arquivo", _modulos("application"), ids=lambda p: p.name)
def test_aplicacao_nao_conhece_frameworks_de_borda(arquivo: Path) -> None:
    proibidos = {"fastapi", "starlette", "uvicorn", "httpx", "redis", "pydantic"}
    for modulo in _imports(arquivo):
        assert _raiz(modulo) not in proibidos, f"{arquivo.name} importa {modulo}"


def test_fastapi_so_aparece_no_adapter_de_entrada() -> None:
    """Trocar de framework web não pode custar mais do que reescrever a borda."""
    permitido = RAIZ_SRC / "adapters" / "inbound"
    for arquivo in RAIZ_SRC.rglob("*.py"):
        if permitido in arquivo.parents:
            continue
        for modulo in _imports(arquivo):
            assert _raiz(modulo) not in {"fastapi", "starlette"}, (
                f"{arquivo.relative_to(RAIZ_SRC)} importa {modulo} fora do adapter de entrada"
            )


def test_redis_e_httpx_so_aparecem_nos_adapters_de_saida() -> None:
    permitido = RAIZ_SRC / "adapters" / "outbound"
    excecoes = {RAIZ_SRC / "config" / "container.py"}  # composition root monta os adapters
    for arquivo in RAIZ_SRC.rglob("*.py"):
        if permitido in arquivo.parents or arquivo in excecoes:
            continue
        for modulo in _imports(arquivo):
            assert _raiz(modulo) not in {"redis", "httpx"}, (
                f"{arquivo.relative_to(RAIZ_SRC)} importa {modulo} fora do adapter de saída"
            )


def test_o_composition_root_e_o_unico_que_instancia_adapters() -> None:
    """Artigo II: um lugar só monta o grafo de dependências."""
    container = RAIZ_SRC / "config" / "container.py"
    for arquivo in RAIZ_SRC.rglob("*.py"):
        if arquivo == container or (RAIZ_SRC / "adapters") in arquivo.parents:
            continue
        for modulo in _imports(arquivo):
            assert not modulo.startswith(f"{PACOTE}.adapters.outbound.cache.redis_cache"), (
                f"{arquivo.relative_to(RAIZ_SRC)} instancia adapter concreto fora do container"
            )
