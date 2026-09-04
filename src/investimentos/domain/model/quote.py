"""Value Object: cotação de um ativo em um instante."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from investimentos.domain.exceptions import QuoteProviderContractError
from investimentos.domain.model.ticker import Ticker


@dataclass(frozen=True, slots=True)
class Quote:
    """Retrato imutável da cotação de um ativo.

    Não tem identidade própria: duas cotações com os mesmos valores são a
    mesma cotação. Por isso é um Value Object, não uma Entidade.

    Os campos opcionais são opcionais porque a fonte externa nem sempre os
    envia — ativo recém-listado, consulta fora do pregão. Exigi-los
    transformaria dado ausente em erro 502, o que seria mentira sobre o que
    aconteceu.
    """

    ticker: Ticker
    short_name: str
    currency: str
    price: Decimal
    quoted_at: datetime
    long_name: str | None = None
    change: Decimal | None = None
    change_percent: Decimal | None = None
    volume: int | None = None
    market_cap: Decimal | None = None

    def __post_init__(self) -> None:
        if self.price < 0:
            raise QuoteProviderContractError(
                f"Preço negativo recebido para {self.ticker}: {self.price}."
            )

        if len(self.currency) != 3:
            raise QuoteProviderContractError(
                f"Moeda deve seguir o padrão ISO 4217 com 3 letras, recebido '{self.currency}'."
            )

        # RN-04: sem fuso horário não dá para comparar instantes com segurança.
        if self.quoted_at.tzinfo is None:
            raise QuoteProviderContractError(
                "O instante da cotação precisa ter fuso horário definido."
            )

    @property
    def symbol(self) -> str:
        """Atalho de leitura para o código do ativo."""
        return self.ticker.value
