"""Tradução: payload da BRAPI -> objeto de domínio.

Este é o único ponto do sistema que conhece os nomes de campo da BRAPI. É o que
cumpre o RF-04 e resolve o problema #2 da spec: se a fonte renomear um campo,
muda este arquivo — o contrato que publicamos continua igual.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from investimentos.domain.exceptions import (
    InvalidTickerError,
    QuoteProviderContractError,
)
from investimentos.domain.model.quote import Quote
from investimentos.domain.model.ticker import Ticker

_DEFAULT_CURRENCY = "BRL"


def _to_decimal(raw: Any) -> Decimal | None:
    """Converte para ``Decimal`` sem herdar o erro binário do float.

    ADR-003: passa por ``str`` de propósito. ``Decimal(0.1)`` preserva o erro
    do ponto flutuante; ``Decimal(str(0.1))`` não.
    """
    if raw is None:
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _to_int(raw: Any) -> int | None:
    if raw is None:
        return None
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


def _to_datetime(raw: Any) -> datetime:
    """Interpreta o instante informado pela fonte, sempre com fuso (RN-04).

    Ausente ou ilegível, assume o instante atual em UTC: preferimos um horário
    aproximado a recusar uma cotação que a fonte considerou válida.
    """
    if isinstance(raw, str) and raw:
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def normalize_item(item: Any) -> dict[str, Any]:
    """Achata as duas gerações de resposta da BRAPI em uma forma só.

    ADR-004: o formato legado traz todos os campos na raiz do item. O v2 aninha
    os dados de mercado sob ``data``, mas mantém ``symbol`` e ``requestedSymbol``
    no nível de fora:

        {"requestedSymbol": "B3SA3", "symbol": "B3SA3",
         "data": {"shortName": ..., "regularMarketPrice": ...}}

    Por isso a normalização **mescla** os dois níveis em vez de descartar o
    externo — descartá-lo perderia o ``symbol``. Em caso de chave repetida,
    ``data`` vence, por ser o nível mais específico.
    """
    if not isinstance(item, dict):
        raise QuoteProviderContractError(
            f"Item de cotação deveria ser um objeto, recebido {type(item).__name__}."
        )

    nested = item.get("data")
    if not isinstance(nested, dict):
        return item

    merged = {chave: valor for chave, valor in item.items() if chave != "data"}
    merged.update(nested)
    return merged


def extract_items(payload: Any) -> list[dict[str, Any]]:
    """Devolve todos os itens de ``results``, já normalizados.

    ADR-014: a Spec 002 lê a lista inteira, não só o primeiro elemento — a
    resposta da fonte sempre foi uma lista, nós é que pedíamos um ativo só.
    """
    if not isinstance(payload, dict):
        raise QuoteProviderContractError(
            f"Resposta deveria ser um objeto JSON, recebido {type(payload).__name__}."
        )

    results = payload.get("results")
    if results is None:
        raise QuoteProviderContractError("Resposta da fonte não contém o campo 'results'.")
    if not isinstance(results, list):
        raise QuoteProviderContractError("O campo 'results' deveria ser uma lista.")

    return [normalize_item(item) for item in results]


def to_quotes(payload: Any, requested: Sequence[Ticker]) -> Mapping[Ticker, Quote]:
    """Traduz a resposta da fonte em um mapa indexado pelo código do ativo.

    ADR-014: o casamento entre pedido e resposta é feito **por código**, nunca
    por posição. Nada garante que a fonte devolva na ordem pedida nem que
    devolva todos; casar por índice produziria, no pior caso, a cotação de um
    ativo atribuída a outro — defeito que passa despercebido porque a resposta
    parece perfeitamente válida.

    Só entram no mapa os ativos que foram pedidos. Um item cujo ``symbol`` não
    passa na regra do ``Ticker`` — um índice, por exemplo — é ignorado em vez de
    derrubar o lote: ele não foi pedido, então não pode estragar o resultado de
    quem foi.
    """
    pedidos = {t.value: t for t in requested}
    resolvidos: dict[Ticker, Quote] = {}

    for item in extract_items(payload):
        simbolo = item.get("symbol")
        if not isinstance(simbolo, str):
            continue
        pedido = pedidos.get(simbolo.strip().upper())
        if pedido is None:
            continue
        resolvidos[pedido] = to_quote(item, pedido)

    return resolvidos


def to_quote(item: dict[str, Any], requested: Ticker) -> Quote:
    """Constrói o ``Quote`` a partir de um item já normalizado.

    Campos além dos mapeados são ignorados de propósito: a fonte pode crescer
    sem quebrar a nossa API.
    """
    symbol_raw = item.get("symbol") or requested.value
    try:
        ticker = Ticker(str(symbol_raw))
    except InvalidTickerError:
        # A fonte devolveu um símbolo que não passa na nossa regra (ex.: índice).
        # Mantemos o código pedido, que já é válido por construção.
        ticker = requested

    price = _to_decimal(item.get("regularMarketPrice"))
    if price is None:
        raise QuoteProviderContractError(
            f"A fonte não informou o preço ('regularMarketPrice') para {requested}."
        )

    currency = item.get("currency") or _DEFAULT_CURRENCY

    return Quote(
        ticker=ticker,
        short_name=str(item.get("shortName") or ticker.value),
        long_name=str(item["longName"]) if item.get("longName") else None,
        currency=str(currency).upper(),
        price=price,
        change=_to_decimal(item.get("regularMarketChange")),
        change_percent=_to_decimal(item.get("regularMarketChangePercent")),
        volume=_to_int(item.get("regularMarketVolume")),
        market_cap=_to_decimal(item.get("marketCap")),
        quoted_at=_to_datetime(item.get("regularMarketTime")),
    )
