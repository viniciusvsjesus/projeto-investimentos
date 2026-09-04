"""Value Object: código de negociação de um ativo na B3."""

from __future__ import annotations

import re
from dataclasses import dataclass

from investimentos.domain.exceptions import InvalidTickerError

# RN-01: quatro caracteres de prefixo — o primeiro é sempre letra, os três
# seguintes podem ser letra ou dígito — mais um ou dois dígitos e um 'F'
# opcional (mercado fracionário).
#
# O prefixo aceita dígito porque a B3 realmente emite códigos assim:
#   B3SA3  (B3)           M1TA34 (BDR da Meta)
# Restringir a quatro letras deixaria papéis legítimos de fora — foi um teste
# com B3SA3 que expôs a regra antiga como estreita demais.
_TICKER_PATTERN = re.compile(r"^[A-Z][A-Z0-9]{3}\d{1,2}F?$")

_FORMATO_ESPERADO = (
    "quatro caracteres começando por letra, seguidos de um ou dois dígitos, "
    "com 'F' opcional para o mercado fracionário "
    "(ex.: PETR4, B3SA3, BOVA11, MXRF11, AAPL34, PETR4F)"
)


@dataclass(frozen=True, slots=True)
class Ticker:
    """Código de um ativo, sempre válido e sempre em maiúsculas.

    A validação acontece na construção. Consequência prática: se um ``Ticker``
    existe, ele é válido — nenhuma outra camada precisa revalidar, e nenhum
    código inválido consegue circular pelo sistema.

    Imutável e hashável, para servir de chave de dicionário e de cache.
    """

    value: str

    def __init__(self, value: str) -> None:
        if not isinstance(value, str):
            raise InvalidTickerError(
                f"Código de ativo deve ser texto, recebido {type(value).__name__}."
            )

        normalized = value.strip().upper()  # RN-02

        if not normalized:
            raise InvalidTickerError("Código de ativo não pode ser vazio.")

        if not _TICKER_PATTERN.match(normalized):
            raise InvalidTickerError(
                f"O código '{value}' não segue o padrão da B3: {_FORMATO_ESPERADO}."
            )

        # frozen=True bloqueia a atribuição direta; este é o caminho oficial.
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value
