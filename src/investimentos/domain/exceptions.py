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


class TooManyTickersError(DomainError):
    """Foram pedidos mais ativos do que cabe numa requisição.

    É erro de domínio, não de transporte: a cota da fonte é finita, e quantos
    ativos cabem numa consulta é regra do problema, não detalhe de HTTP.

    Carrega os números para que a mensagem seja útil sem o adapter ter de
    recalcular nada.
    """

    def __init__(self, requested: int, limit: int) -> None:
        super().__init__(
            f"Foram pedidos {requested} ativos, mas o limite por requisição é {limit}. "
            f"Divida a consulta em partes menores."
        )
        self.requested = requested
        self.limit = limit


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
    """A cota de uso da fonte foi esgotada.

    Carrega o tempo de espera que a fonte informou, quando informa. Ele é
    repassado a quem chamou (ADR-013) em vez de virar uma nova tentativa
    silenciosa: insistir por conta própria prenderia o cliente por segundos sem
    que ele tivesse pedido isso.
    """

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class QuoteProviderTimeoutError(QuoteProviderError):
    """A fonte não respondeu dentro do tempo limite configurado."""


class QuoteProviderContractError(QuoteProviderError):
    """A fonte respondeu, mas fora do formato acordado.

    Levantada quando falta um campo obrigatório ou o corpo não é o esperado.
    Nunca se produz uma cotação com preço zero para 'salvar' a resposta:
    dado ausente vira erro explícito, não número inventado.
    """
