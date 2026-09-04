"""Exceções de domínio.

Artigo VIII: o domínio não sabe o que é HTTP. Nenhuma exceção daqui carrega
status code, header ou corpo de resposta — a tradução para HTTP é
responsabilidade exclusiva do adapter de entrada.
"""

from __future__ import annotations


class DomainError(Exception):
    """Raiz de toda falha originada nas regras de negócio."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidTickerError(DomainError):
    """Código de ativo fora do padrão da B3 (RN-01)."""


class QuoteNotFoundError(DomainError):
    """A fonte respondeu, mas não conhece o ativo pedido."""

    def __init__(self, ticker: str) -> None:
        super().__init__(f"Nenhuma cotação encontrada para o ativo '{ticker}'.")
        self.ticker = ticker


class QuoteProviderError(DomainError):
    """Família de falhas da fonte externa de cotações.

    Existe para que a camada de aplicação possa tratar 'a fonte falhou' sem
    conhecer o motivo específico, e para que o adapter de entrada possa
    distinguir os motivos ao escolher o status HTTP.
    """


class QuoteProviderAuthError(QuoteProviderError):
    """A fonte rejeitou a credencial.

    A mensagem nunca inclui qualquer parte do token (Artigo V).
    """


class QuoteProviderRateLimitedError(QuoteProviderError):
    """A cota de uso da fonte foi esgotada."""


class QuoteProviderTimeoutError(QuoteProviderError):
    """A fonte não respondeu dentro do tempo limite configurado."""


class QuoteProviderContractError(QuoteProviderError):
    """A fonte respondeu, mas fora do formato acordado.

    Levantada quando falta um campo obrigatório ou o corpo não é o esperado.
    Nunca se produz uma cotação com preço zero para 'salvar' a resposta:
    dado ausente vira erro explícito, não número inventado.
    """
