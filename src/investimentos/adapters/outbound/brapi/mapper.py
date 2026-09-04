"""Tradução: payload da BRAPI -> objeto de domínio.

Este é o único ponto do sistema que conhece os nomes de campo da BRAPI. É o que
cumpre o RF-04 e resolve o problema #2 da spec: se a fonte renomear um campo,
muda este arquivo — o contrato que publicamos continua igual.
"""

from __future__ import annotations

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


def extract_first_item(payload: Any) -> dict[str, Any] | None:
    """Retira o primeiro item de ``results``. ``None`` quando não há resultado."""
    if not isinstance(payload, dict):
        raise QuoteProviderContractError(
            f"Resposta deveria ser um objeto JSON, recebido {type(payload).__name__}."
        )

    results = payload.get("results")
    if results is None:
        raise QuoteProviderContractError("Resposta da fonte não contém o campo 'results'.")
    if not isinstance(results, list):
        raise QuoteProviderContractError("O campo 'results' deveria ser uma lista.")
    if not results:
        return None

    return normalize_item(results[0])


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
