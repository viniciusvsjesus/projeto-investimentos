"""T066 — O token não vaza (RNF-02, Artigo V)."""

from __future__ import annotations

import logging
from pathlib import Path

from investimentos.config.settings import Settings

SEGREDO = "token-ultra-secreto-do-vini"
RAIZ = Path(__file__).resolve().parents[2]


def _settings() -> Settings:
    return Settings(_env_file=None, brapi_token=SEGREDO, redis_url=None)


def test_token_nao_aparece_no_repr() -> None:
    assert SEGREDO not in repr(_settings())


def test_token_nao_aparece_no_str() -> None:
    assert SEGREDO not in str(_settings())


def test_token_nao_aparece_na_serializacao() -> None:
    assert SEGREDO not in str(_settings().model_dump())


def test_token_e_recuperavel_no_ponto_de_uso() -> None:
    assert _settings().brapi_token_value == SEGREDO


def test_token_nao_vaza_em_log(caplog) -> None:
    with caplog.at_level(logging.DEBUG):
        logging.getLogger("teste").info("settings=%s", _settings())
    assert SEGREDO not in caplog.text


def test_gitignore_bloqueia_o_env() -> None:
    """A primeira tarefa do projeto (T000) precisa continuar valendo."""
    linhas = (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in linhas
    assert "!.env.example" in linhas


def test_env_example_nao_contem_valor_real() -> None:
    conteudo = (RAIZ / ".env.example").read_text(encoding="utf-8")
    for linha in conteudo.splitlines():
        if linha.startswith("BRAPI_TOKEN="):
            valor = linha.split("=", 1)[1].strip()
            assert valor == "cole-seu-token-aqui", "placeholder do token foi alterado"


def test_env_real_nao_esta_versionado() -> None:
    """Se este teste falhar, rotacione o token (Artigo V)."""
    import subprocess

    resultado = subprocess.run(
        ["git", "ls-files", "--error-unmatch", ".env"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
    )
    assert resultado.returncode != 0, ".env está rastreado pelo Git"


def test_placeholder_do_env_example_conta_como_sem_token() -> None:
    """Um .env não preenchido não deve virar 401 confuso da BRAPI."""
    settings = Settings(_env_file=None, brapi_token="cole-seu-token-aqui", redis_url=None)
    assert settings.brapi_token_value is None


def test_token_vazio_conta_como_sem_token() -> None:
    assert Settings(_env_file=None, brapi_token="", redis_url=None).brapi_token_value is None


def test_token_de_verdade_e_preservado() -> None:
    settings = Settings(_env_file=None, brapi_token=SEGREDO, redis_url=None)
    assert settings.brapi_token_value == SEGREDO
