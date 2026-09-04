# Contrato CONSUMIDO — BRAPI, cotação

Este documento descreve o que **esperamos** da fonte externa. Ele é a
especificação verificada pelo teste de contrato (`tests/contract/`, `-m contract`).

> Fonte externa não é contrato garantido. Se este documento e a realidade
> divergirem, quem está errado é este documento — e o contract test é o que
> revela isso antes do usuário.

## Autenticação

```
Authorization: Bearer <BRAPI_TOKEN>
```

Token **nunca** em query string: a própria documentação da BRAPI alerta que
isso vaza para histórico de navegador e log de servidor (Artigo V).

`PETR4`, `VALE3`, `MGLU3` e `ITUB4` respondem sem token (sandbox), o que
permite validar o fluxo antes de configurar a credencial.

## Endpoint

Configurável via `BRAPI_QUOTE_PATH`. A BRAPI publica duas gerações; a **v2** é
a ativa, confirmada com payload real em 2026-09-03 (ADR-004).

| Geração | Requisição |
|---|---|
| **v2 (padrão)** | `GET {BRAPI_BASE_URL}/api/v2/stocks/quote?symbols={TICKER}` |
| Legado | `GET {BRAPI_BASE_URL}/api/quote/{TICKER}` |

`BRAPI_BASE_URL` padrão: `https://brapi.dev`

## Resposta esperada — `200 OK` (v2, formato confirmado)

```json
{
  "results": [
    {
      "requestedSymbol": "B3SA3",
      "symbol": "B3SA3",
      "changed": false,
      "data": {
        "shortName": "B3SA3",
        "longName": "B3 SA - Brasil, Bolsa, Balcao",
        "currency": "BRL",
        "regularMarketPrice": 17.26,
        "regularMarketChange": 0.64,
        "regularMarketChangePercent": 3.85,
        "regularMarketTime": "2026-09-03T03:54:59.000Z",
        "marketCap": 80748160464,
        "regularMarketVolume": 41077700,
        "logourl": "https://icons.brapi.dev/icons/B3SA3.svg"
      }
    }
  ],
  "requestedAt": "2026-09-03T12:12:29.182Z",
  "took": 1
}
```

**Detalhe que importa:** `symbol` fica **fora** de `data`. O mapper mescla os
dois níveis (com `data` vencendo em conflito) em vez de descartar o externo —
descartá-lo perderia o código do ativo.

Na geração legado, os mesmos campos vêm todos na raiz do item. As duas formas
são tratadas e testadas.

### Campos que o nosso mapper consome

| Campo | Obrigatório para nós | Se ausente |
|---|---|---|
| `symbol` | sim | `QuoteProviderContractError` |
| `regularMarketPrice` | sim | `QuoteProviderContractError` |
| `shortName` | não | cai para o valor de `symbol` |
| `longName` | não | `null` |
| `currency` | não | assume `BRL` |
| `regularMarketChange` | não | `null` |
| `regularMarketChangePercent` | não | `null` |
| `regularMarketVolume` | não | `null` |
| `marketCap` | não | `null` |
| `regularMarketTime` | não | assume o instante atual em UTC |

Campos além destes são **ignorados de propósito**. A fonte pode adicionar o que
quiser sem quebrar a nossa API — é o isolamento de contrato do problema #2.

## Respostas de erro da fonte → nossa exceção de domínio

| Situação na fonte | Nossa exceção | Nosso status |
|---|---|---|
| `200` com `results` vazio ou ausente | `QuoteNotFoundError` | `404` |
| `404` | `QuoteNotFoundError` | `404` |
| `401` / `403` | `QuoteProviderAuthError` | `502` |
| `429` | `QuoteProviderRateLimited` | `503` |
| `5xx` | `QuoteProviderError` | `502` |
| Timeout de conexão ou leitura | `QuoteProviderTimeout` | `504` |
| Corpo não-JSON, ou item sem `regularMarketPrice` | `QuoteProviderContractError` | `502` |

## O que o contract test verifica

1. O endpoint configurado responde `200` para `PETR4`.
2. O payload contém `results` como lista não vazia.
3. O item — normalizado por `item.get("data", item)` — contém `symbol` e
   `regularMarketPrice`.
4. O mapper produz um `Quote` válido a partir do payload **real**.
5. Um ticker sabidamente inexistente resulta em `QuoteNotFoundError`.

Roda com `pytest -m contract`. Fora do CI, por consumir cota e depender de rede.
