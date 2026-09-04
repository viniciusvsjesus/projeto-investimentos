"""Serialização de ``Quote`` para o cache.

Fica no adapter, não no domínio: o domínio não sabe o que é JSON (Artigo II).
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Any

from investimentos.domain.model.quote import Quote
from investimentos.domain.model.ticker import Ticker


def _decimal_to_str(value: Decimal | None) -> str | None:
    """``Decimal`` vira string de propósito.

    ADR-003: gravar como número JSON traria o valor de volta como float e
    reintroduziria o erro binário que evitamos ao construir a cotação.
    """
    return None if value is None else str(value)


def dumps(quote: Quote) -> str:
    payload: dict[str, Any] = {
        "ticker": quote.ticker.value,
        "short_name": quote.short_name,
        "long_name": quote.long_name,
        "currency": quote.currency,
        "price": _decimal_to_str(quote.price),
        "change": _decimal_to_str(quote.change),
        "change_percent": _decimal_to_str(quote.change_percent),
        "volume": quote.volume,
        "market_cap": _decimal_to_str(quote.market_cap),
        "quoted_at": quote.quoted_at.isoformat(),
    }
    return json.dumps(payload, ensure_ascii=False)


def loads(raw: str) -> Quote:
    """Reconstrói a cotação. Levanta ``ValueError`` se o dado estiver corrompido."""
    data = json.loads(raw)
    return Quote(
        ticker=Ticker(data["ticker"]),
        short_name=data["short_name"],
        long_name=data.get("long_name"),
        currency=data["currency"],
        price=Decimal(data["price"]),
        change=Decimal(data["change"]) if data.get("change") is not None else None,
        change_percent=(
            Decimal(data["change_percent"]) if data.get("change_percent") is not None else None
        ),
        volume=data.get("volume"),
        market_cap=(Decimal(data["market_cap"]) if data.get("market_cap") is not None else None),
        quoted_at=datetime.fromisoformat(data["quoted_at"]),
    )
