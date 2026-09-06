# Modelo de dados — Spec 003

Complementa as Specs 001 e 002. Só o que **muda ou nasce**.

---

## 1. Domínio — intocado

`Ticker`, `Quote` e as exceções seguem exatamente como estão, **em inglês**.

Não é descuido: é a ADR-016. O Artigo X manda usar a linguagem ubíqua do
domínio, e a linguagem deste código é o inglês. Português é decisão de
contrato — o consumidor vê a resposta, não o nome da classe.

---

## 2. Porta de cache — ganha a validade

### `CachedQuote` — novo tipo, vive junto da porta

| Atributo | Tipo | Observação |
|---|---|---|
| `quote` | `Quote` | A cotação |
| `ttl_seconds` | `int \| None` | Quanto ainda vale. `None` quando o cache não sabe informar |

Fica em `application/ports/quote_cache.py` porque validade é assunto do cache,
não da cotação — uma mesma cotação tem validades diferentes conforme quando
entrou.

### Assinatura nova

```
QuoteCachePort
    async get_many(tickers) -> Mapping[Ticker, CachedQuote]    ← era Mapping[Ticker, Quote]
    async set_many(quotes)  -> None                            (inalterada)
    async ping()            -> bool                            (inalterada)
```

O contrato de robustez continua: nenhum método levanta exceção por falha de
infraestrutura.

---

## 3. Aplicação — `QuoteResolution` ganha `valid_for`

| Atributo | Tipo | Quando |
|---|---|---|
| `valid_for` | `int \| None` | Segundos que a cotação ainda vale |

| Origem | Valor |
|---|---|
| `CACHE` | O TTL restante informado pelo Redis |
| `SOURCE` | O TTL cheio — acabou de ser gravada |
| Não encontrada | `None` |
| Cache desligado | `0` → vira `no-store` na borda |

`QuoteLookup` ganha `min_valid_for`, que é o menor `valid_for` entre os itens
com cotação, ou `None` quando não há nenhuma (ADR-019).

---

## 4. Contrato de saída — todo em português

### `GET /acoes/{ticker}` — item

```json
{
  "ticker": "ITSA4",
  "nomeCurto": "ITSA4",
  "nomeLongo": "Itausa SA",
  "moeda": "BRL",
  "preco": 11.42,
  "variacao": -0.35,
  "variacaoPercentual": -0.95,
  "volume": 27681100,
  "valorDeMercado": 483937892568,
  "cotadoEm": "2026-09-06T17:24:54Z",
  "fonte": "brapi",
  "emCache": false
}
```

`404` quando o ativo não existe.

### `GET /acoes?ticker=ITSA4&ticker=ZZZZ9` — coleção

Sempre uma lista, inclusive com um elemento (Artigo XI).

```json
[
  {
    "ticker": "ITSA4",
    "situacao": "encontrada",
    "cotacao": { "preco": 11.42, "emCache": true, "...": "..." }
  },
  {
    "ticker": "ZZZZ9",
    "situacao": "naoEncontrada",
    "cotacao": null
  }
]
```

### O que **não** foi traduzido, e por quê

| Campo | Motivo |
|---|---|
| `ticker` | Palavra corrente do mercado brasileiro e nome do Value Object do domínio |
| `volume` | Idêntica nas duas línguas |
| `type`, `title`, `status`, `detail`, `instance` | RFC 9457 — ver ADR-017 |

### Corpo de erro — nomes do RFC, valores em português

```json
{
  "type": "https://projeto-investimentos/errors/too-many-tickers",
  "title": "Ativos demais na requisição",
  "status": 400,
  "detail": "Foram pedidos 4 ativos, mas o limite por requisição é 3.",
  "instance": "/acoes"
}
```

### Índice e saúde

```json
{
  "servico": "Projeto Investimentos API",
  "versao": "3.0.0",
  "situacao": "ok",
  "exemplo": "http://localhost:8000/acoes/ITSA4",
  "rotas": {
    "acao": "/acoes/{ticker}",
    "acoes": "/acoes?ticker=ITSA4&ticker=PETR4",
    "saude": "/health",
    "openapi": "/openapi.json",
    "documentacao": "/docs"
  }
}
```

```json
{ "situacao": "ok", "dependencias": { "cache": "ok" } }
```

Valores em português: `ok` | `degradado`, e `ok` | `indisponivel` | `desligado`.

---

## 5. Cabeçalho de validade

| Situação | `Cache-Control` |
|---|---|
| Item com cotação válida por N segundos | `public, max-age=N` |
| Lista com validades diferentes | `public, max-age=<menor>` |
| Nenhuma cotação válida, ou cache desligado | `no-store` |
| Qualquer resposta de erro | `no-store` |

O `max-age` vem do TTL **restante** informado pelo Redis, nunca do configurado
(ADR-018). Valores não positivos do Redis (`-1`, `-2`) viram ausência de
validade no adapter.

---

## 6. Formato do cache

Sem mudança. Chave `quote:v1:{TICKER}`, valor JSON do `Quote`, TTL por ativo. As
chaves gravadas pelas Specs 001 e 002 continuam válidas — a Spec 003 muda o que
**perguntamos** ao Redis (`GET` mais `TTL`), não o que gravamos.
