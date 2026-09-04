"""DTOs da fronteira HTTP.

Estes modelos existem para que o formato da resposta seja uma decisão nossa,
independente tanto do domínio quanto da fonte externa (RF-04). ``camelCase`` na
fronteira, ``snake_case`` no Python — a tradução é declarativa, não manual.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer
from pydantic.alias_generators import to_camel

from investimentos.application.usecases.get_quote import QuoteResult


class CamelModel(BaseModel):
    """Base que expõe todo campo em camelCase, aceitando os dois nomes na entrada."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class QuoteResponse(CamelModel):
    """Cotação no nosso contrato — estável mesmo se a fonte mudar o dela."""

    ticker: str = Field(examples=["PETR4"])
    short_name: str = Field(examples=["PETR4"])
    long_name: str | None = Field(default=None, examples=["Petroleo Brasileiro SA Petrobras"])
    currency: str = Field(min_length=3, max_length=3, examples=["BRL"])
    price: Decimal = Field(examples=[Decimal("36.65")])
    change: Decimal | None = Field(default=None, examples=[Decimal("-0.35")])
    change_percent: Decimal | None = Field(default=None, examples=[Decimal("-0.95")])
    volume: int | None = Field(default=None, examples=[27681100])
    market_cap: Decimal | None = Field(default=None, examples=[Decimal("483937892568")])
    quoted_at: datetime = Field(
        description="Instante informado pela fonte, em UTC (RN-04).",
        examples=["2026-09-03T17:24:54Z"],
    )
    source: str = Field(
        description="Fonte de onde a cotação veio. Sempre presente.",
        examples=["brapi"],
    )
    cached: bool = Field(
        description="Indica se a resposta veio do cache. Torna o RF-05 observável.",
        examples=[False],
    )

    @field_serializer("price", when_used="json")
    def _preco_como_numero(self, valor: Decimal) -> float:
        """Emite número JSON, não string.

        O Pydantic serializa ``Decimal`` como string por padrão, o que faria
        ``"price": "17.26"`` — surpreendente para quem lê o JSON e em desacordo
        com o contrato em ``contracts/openapi.yaml``, que promete ``number``.

        A conversão acontece **só aqui**, no último passo antes de virar bytes.
        Todo o cálculo e a comparação de valor a montante seguem em ``Decimal``
        (ADR-003) — é a diferença entre perder precisão no meio do caminho e
        apenas escrevê-la no formato que o JSON tem.

        O tipo de retorno é ``float``, sem ``None``: o preço é obrigatório e
        nunca é nulo. Anotá-lo como opcional publicaria ``["number","null"]`` no
        OpenAPI e faria qualquer gerador de cliente produzir um tipo anulável
        para um campo que sempre vem preenchido.
        """
        return float(valor)

    @field_serializer("change", "change_percent", "market_cap", when_used="json")
    def _decimais_opcionais_como_numero(self, valor: Decimal | None) -> float | None:
        """Mesma conversão, para os campos que a fonte pode não enviar."""
        return None if valor is None else float(valor)

    @classmethod
    def from_result(cls, result: QuoteResult, source: str) -> QuoteResponse:
        q = result.quote
        return cls(
            ticker=q.ticker.value,
            short_name=q.short_name,
            long_name=q.long_name,
            currency=q.currency,
            price=q.price,
            change=q.change,
            change_percent=q.change_percent,
            volume=q.volume,
            market_cap=q.market_cap,
            quoted_at=q.quoted_at,
            source=source,
            cached=result.cached,
        )


class RotasDisponiveis(CamelModel):
    """As URLs que o serviço expõe, para quem abriu a raiz sem saber o caminho."""

    cotacao: str = Field(default="/cotacao/{ticker}")
    saude: str = Field(default="/health")
    openapi: str = Field(default="/openapi.json")
    documentacao: str = Field(default="/docs")


class IndexResponse(CamelModel):
    """Resposta da raiz. JSON puro — nenhuma tela, nenhum botão."""

    servico: str = Field(examples=["Projeto Investimentos API"])
    versao: str = Field(examples=["1.0.0"])
    status: str = Field(examples=["ok"])
    exemplo: str = Field(
        description="URL pronta para copiar e colar no navegador.",
        examples=["http://localhost:8000/cotacao/PETR4"],
    )
    rotas: RotasDisponiveis


class DependenciesStatus(CamelModel):
    cache: str = Field(examples=["ok"], description="ok | unavailable | disabled")


class HealthResponse(CamelModel):
    status: str = Field(examples=["ok"], description="ok | degraded")
    dependencies: DependenciesStatus


class ProblemDetail(CamelModel):
    """Corpo único de erro para toda a API (RF-10, Artigo VIII).

    Nunca carrega stack trace, detalhe interno ou qualquer parte da credencial.
    """

    type: str = Field(examples=["https://projeto-investimentos/errors/invalid-ticker"])
    title: str = Field(examples=["Código de ativo inválido"])
    status: int = Field(examples=[400])
    detail: str | None = Field(default=None)
    instance: str | None = Field(default=None, examples=["/api/v1/quotes/PETR"])
