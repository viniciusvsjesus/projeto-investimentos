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

from investimentos.application.usecases.get_quote import QuoteLookup, QuoteResolution


class CamelModel(BaseModel):
    """Base que expõe todo campo em camelCase, aceitando os dois nomes na entrada."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class CotacaoResponse(CamelModel):
    """Cotação de um ativo, no nosso contrato — estável mesmo se a fonte mudar.

    Os nomes estão em português por decisão da Spec 003. A tradução acontece
    **aqui e só aqui**: o domínio segue em inglês, porque é a linguagem ubíqua
    do código (ADR-016). O consumidor vê esta classe, não o `Quote`.
    """

    ticker: str = Field(examples=["ITSA4"])
    nome_curto: str = Field(examples=["ITSA4"])
    nome_longo: str | None = Field(default=None, examples=["Itausa SA"])
    moeda: str = Field(min_length=3, max_length=3, examples=["BRL"])
    preco: Decimal = Field(examples=[Decimal("11.42")])
    variacao: Decimal | None = Field(default=None, examples=[Decimal("-0.35")])
    variacao_percentual: Decimal | None = Field(default=None, examples=[Decimal("-0.95")])
    volume: int | None = Field(default=None, examples=[27681100])
    valor_de_mercado: Decimal | None = Field(default=None, examples=[Decimal("483937892568")])
    cotado_em: datetime = Field(
        description="Instante informado pela fonte, em UTC.",
        examples=["2026-09-06T17:24:54Z"],
    )
    fonte: str = Field(description="De onde o dado veio.", examples=["brapi"])
    em_cache: bool = Field(
        description="Indica se a cotação veio do cache.",
        examples=[False],
    )

    @field_serializer("preco", when_used="json")
    def _preco_como_numero(self, valor: Decimal) -> float:
        """Emite número JSON, não string.

        O Pydantic serializa ``Decimal`` como string por padrão, o que faria
        ``"preco": "11.42"`` — em desacordo com o `number` prometido no
        contrato. A conversão acontece só aqui, no último passo antes de virar
        bytes; todo o trajeto anterior segue em ``Decimal`` (ADR-003).

        Retorno ``float`` sem ``None``: o preço é obrigatório e nunca é nulo.
        """
        return float(valor)

    @field_serializer("variacao", "variacao_percentual", "valor_de_mercado", when_used="json")
    def _decimais_opcionais_como_numero(self, valor: Decimal | None) -> float | None:
        """Mesma conversão, para os campos que a fonte pode não enviar."""
        return None if valor is None else float(valor)

    @classmethod
    def from_resolution(cls, resolution: QuoteResolution, source: str) -> CotacaoResponse:
        q = resolution.quote
        assert q is not None, "from_resolution exige uma resolução com cotação"
        return cls(
            ticker=q.ticker.value,
            nome_curto=q.short_name,
            nome_longo=q.long_name,
            moeda=q.currency,
            preco=q.price,
            variacao=q.change,
            variacao_percentual=q.change_percent,
            volume=q.volume,
            valor_de_mercado=q.market_cap,
            cotado_em=q.quoted_at,
            fonte=source,
            em_cache=resolution.cached,
        )


class AcaoConsultada(CamelModel):
    """Um ativo pedido e o que aconteceu com ele.

    A cotação vem **envelopada**, não achatada. Um ativo não encontrado não tem
    preço, e `preco` é obrigatório e não anulável — achatar obrigaria a torná-lo
    opcional, exatamente o defeito que a Spec 001 corrigiu.
    """

    ticker: str = Field(examples=["ITSA4"])
    situacao: str = Field(examples=["encontrada"], description="encontrada | naoEncontrada")
    cotacao: CotacaoResponse | None = Field(default=None)

    @classmethod
    def from_resolution(cls, resolution: QuoteResolution, source: str) -> AcaoConsultada:
        if not resolution.found:
            return cls(ticker=resolution.ticker.value, situacao="naoEncontrada", cotacao=None)
        return cls(
            ticker=resolution.ticker.value,
            situacao="encontrada",
            cotacao=CotacaoResponse.from_resolution(resolution, source=source),
        )

    @staticmethod
    def from_lookup(lookup: QuoteLookup, source: str) -> list[AcaoConsultada]:
        """Monta a lista na ordem em que os ativos foram pedidos."""
        return [AcaoConsultada.from_resolution(r, source) for r in lookup.resolutions]


class RotasDisponiveis(CamelModel):
    """As URLs que o serviço expõe, para quem abriu a raiz sem saber o caminho."""

    acao: str = Field(default="/acoes/{ticker}")
    acoes: str = Field(default="/acoes?ticker=ITSA4&ticker=PETR4")
    saude: str = Field(default="/health")
    openapi: str = Field(default="/openapi.json")
    documentacao: str = Field(default="/docs")


class IndiceResponse(CamelModel):
    """Resposta da raiz. JSON puro — nenhuma tela, nenhum botão."""

    servico: str = Field(examples=["Projeto Investimentos API"])
    versao: str = Field(examples=["3.0.0"])
    situacao: str = Field(examples=["ok"])
    exemplo: str = Field(
        description="URL pronta para copiar e colar no navegador.",
        examples=["http://localhost:8000/acoes/ITSA4"],
    )
    rotas: RotasDisponiveis


class DependenciasSaude(CamelModel):
    cache: str = Field(examples=["ok"], description="ok | indisponivel | desligado")


class SaudeResponse(CamelModel):
    situacao: str = Field(examples=["ok"], description="ok | degradado")
    dependencias: DependenciasSaude


class ProblemDetail(CamelModel):
    """Corpo único de erro para toda a API (Artigo VIII).

    ADR-017: os **nomes** dos campos seguem o RFC 9457 e **não** são traduzidos.
    Eles são o que dá sentido ao ``application/problem+json`` que a API declara;
    traduzi-los produziria um corpo que diz ser problem+json sem o ser, e um
    consumidor genérico de erro deixaria de entendê-lo. Os **valores** — `title`
    e `detail`, a parte destinada a humanos — estão em português desde a Spec 001.

    Nunca carrega stack trace, detalhe interno ou qualquer parte da credencial.
    """

    type: str = Field(examples=["https://projeto-investimentos/errors/invalid-ticker"])
    title: str = Field(examples=["Código de ativo inválido"])
    status: int = Field(examples=[400])
    detail: str | None = Field(default=None)
    instance: str | None = Field(default=None, examples=["/api/v1/quotes/PETR"])
