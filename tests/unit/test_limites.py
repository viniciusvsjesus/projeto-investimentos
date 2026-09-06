"""T043 — O limite configurado guarda o Complexity Tracking do plano.

O plano registrou que **não** existe fatiamento de lote, e que isso só é seguro
enquanto o nosso limite for menor ou igual ao da fonte. Este teste é a guarda
dessa condição: se alguém subir `MAX_TICKERS_PER_REQUEST` além do teto do plano
sem implementar o fatiamento, o build quebra antes de a cota ser desperdiçada.
"""

from __future__ import annotations

from investimentos.config.settings import Settings

# Tetos publicados pela BRAPI. O plano gratuito não é documentado; 3 é a aposta
# conservadora registrada na spec, e o contract test é quem confirma.
TETO_PLANO_STARTUP = 10


def _settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, redis_url=None, **overrides)  # type: ignore[arg-type]


def test_padrao_e_tres() -> None:
    assert _settings().max_tickers_per_request == 3


def test_padrao_cabe_no_menor_teto_publicado_da_fonte() -> None:
    assert _settings().max_tickers_per_request <= TETO_PLANO_STARTUP


def test_limite_e_configuravel() -> None:
    assert _settings(max_tickers_per_request=5).max_tickers_per_request == 5


def test_limite_minimo_e_um() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _settings(max_tickers_per_request=0)
