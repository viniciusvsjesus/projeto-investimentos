"""Configuração da aplicação, lida do ambiente.

RNF-08: nenhum valor de ambiente fica fixo no código ou na imagem.
Artigo V: o token é ``SecretStr`` — o Pydantic o mascara em ``repr()``, em log
e em qualquer serialização acidental.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valor de exemplo do .env.example. Se ele chegar como se fosse token de verdade,
# a BRAPI devolveria 401 e o usuário veria "credencial rejeitada" sem entender
# que só esqueceu de preencher. Tratamos como ausente: aí os tickers de sandbox
# funcionam e a mensagem fica honesta.
_TOKEN_PLACEHOLDER = "cole-seu-token-aqui"


class Settings(BaseSettings):
    """Variáveis de ambiente da aplicação."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Aplicação ---
    app_name: str = "Projeto Investimentos API"
    app_version: str = "3.0.0"
    app_env: str = "development"
    log_level: str = "INFO"

    # --- Fonte externa ---
    brapi_base_url: str = "https://brapi.dev"
    brapi_token: SecretStr | None = None
    # ADR-004: v2 é o endpoint ativo, confirmado no painel da BRAPI em 2026-09-03.
    # Continua configurável para permitir voltar ao legado (/api/quote/{ticker})
    # sem recompilar, caso a BRAPI mude de geração outra vez.
    brapi_quote_path: str = "/api/v2/stocks/quote?symbols={ticker}"
    brapi_timeout_seconds: float = Field(default=8.0, gt=0)

    # --- Limites de consulta ---
    # Quantos ativos cabem numa requisição a GET /ticker.
    #
    # O padrão 3 é o teto assumido do plano gratuito da fonte. A documentação
    # pública dela declara 10 no plano Startup e 20 no Pro, mas não publica o
    # número do gratuito — por isso é configuração e não constante.
    #
    # ATENÇÃO: elevar este valor acima do teto do plano exige implementar o
    # fatiamento do lote antes. Hoje uma chamada sempre basta justamente porque
    # este número é menor que o limite da fonte. Ver o Complexity Tracking em
    # specs/002-multiplos-tickers/plan.md.
    max_tickers_per_request: int = Field(default=3, ge=1)

    # --- Cache ---
    # Vazio desliga o cache: o container monta o NullQuoteCache e a API segue
    # funcionando (RF-06).
    redis_url: str | None = None
    cache_ttl_seconds: int = Field(default=60, ge=1)

    @field_validator("brapi_token", mode="before")
    @classmethod
    def _ignora_placeholder(cls, valor: object) -> object:
        """Um .env não preenchido vale o mesmo que não ter token."""
        if isinstance(valor, str) and valor.strip() in ("", _TOKEN_PLACEHOLDER):
            return None
        return valor

    @property
    def brapi_token_value(self) -> str | None:
        """Revela o token apenas no ponto de uso, nunca em log ou repr."""
        return self.brapi_token.get_secret_value() if self.brapi_token else None

    @property
    def cache_enabled(self) -> bool:
        return bool(self.redis_url)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Instância única das configurações, resolvida na primeira chamada."""
    return Settings()
