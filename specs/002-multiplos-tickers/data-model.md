# Modelo de dados — Spec 002

Complementa o `data-model.md` da Spec 001. Só o que **muda ou nasce** aqui.

---

## 1. Domínio — o que NÃO muda

`Ticker` e `Quote` seguem exatamente como estão. Nenhum campo novo, nenhum
comportamento novo.

Isso é resultado do Artigo X, não coincidência: origem (cache ou fonte) e status
(encontrado ou não) são desfechos de uma **busca**, não propriedades de uma
**cotação**. Uma cotação vinda do cache é a mesma cotação vinda da fonte. Colocar
`cached` dentro de `Quote` faria o domínio saber que existe cache.

### Exceção nova (`domain/exceptions.py`)

```
DomainError
├── InvalidTickerError            → 400
├── TooManyTickersError           → 400   ← nova
├── QuoteNotFoundError            → 404
└── QuoteProviderError
    ├── QuoteProviderAuthError    → 502
    ├── QuoteProviderRateLimited  → 503
    ├── QuoteProviderTimeout      → 504
    └── QuoteProviderContract     → 502
```

`TooManyTickersError` é de domínio porque o limite é regra do problema — a cota
é finita —, não detalhe de transporte. Ela carrega quantos foram pedidos e qual
o limite, para a mensagem de erro ser útil sem o adapter precisar recalcular.

---

## 2. Aplicação — os tipos novos

Vivem em `application/usecases/`, não em `domain/`. São o resultado de uma
orquestração.

### `QuoteOrigin` — enumeração

| Valor | Significado |
|---|---|
| `CACHE` | Servida do cache, sem consumir cota |
| `SOURCE` | Buscada na fonte externa nesta requisição |

### `QuoteResolution` — o que aconteceu com um ativo pedido

| Atributo | Tipo | Observação |
|---|---|---|
| `ticker` | `Ticker` | O ativo pedido, normalizado |
| `quote` | `Quote \| None` | `None` quando não encontrado |
| `origin` | `QuoteOrigin \| None` | `None` quando não há cotação |

Imutável. Duas propriedades de leitura: `found` (tem cotação) e `cached`
(origem é `CACHE`).

### `QuoteLookup` — a consulta inteira

| Atributo | Tipo | Observação |
|---|---|---|
| `resolutions` | `tuple[QuoteResolution, ...]` | **Na ordem em que os ativos foram pedidos** (FR-016) |

Atalhos de leitura para a borda montar a resposta sem lógica própria: `found`,
`not_found`, `from_cache_count`, `from_source_count`. Estes dois últimos
alimentam o log do Artigo IX — quantos ativos a requisição poupou de cota.

---

## 3. Portas — assinaturas novas

```
QuoteProviderPort
    async fetch_many(tickers: Sequence[Ticker]) -> Mapping[Ticker, Quote]
        Devolve apenas os encontrados. Ausência = a fonte não conhece o ativo.
        Levanta QuoteProviderError para falha de comunicação ou contrato.

QuoteCachePort
    async get_many(tickers: Sequence[Ticker]) -> Mapping[Ticker, Quote]
        Devolve apenas os presentes. Falha de infraestrutura → mapa vazio.
    async set_many(quotes: Iterable[Quote]) -> None
        Grava cada uma com TTL próprio. Falha é silenciosa, por contrato.
    async ping() -> bool
```

O contrato de robustez do cache continua: nenhum método levanta exceção por
falha de infraestrutura. É o que permite ao caso de uso não ter um único
`try/except` (Artigo II).

---

## 4. Contrato de saída

### `GET /ticker/{codigo}` — item

Mesma resposta de hoje, mesmo formato, mesmos campos. Só o caminho mudou.

```json
{
  "ticker": "PETR4",
  "shortName": "PETR4",
  "longName": "Petroleo Brasileiro SA Petrobras",
  "currency": "BRL",
  "price": 36.65,
  "change": -0.35,
  "changePercent": -0.95,
  "volume": 27681100,
  "marketCap": 483937892568,
  "quotedAt": "2026-09-06T17:24:54Z",
  "source": "brapi",
  "cached": false
}
```

`404` quando o ativo não existe.

### `GET /ticker?ticker=petr4&ticker=zzzz9` — coleção

Sempre uma lista, inclusive com um elemento ou nenhum (Artigo XI).

```json
[
  {
    "ticker": "PETR4",
    "status": "found",
    "quote": {
      "ticker": "PETR4",
      "shortName": "PETR4",
      "longName": "Petroleo Brasileiro SA Petrobras",
      "currency": "BRL",
      "price": 36.65,
      "change": -0.35,
      "changePercent": -0.95,
      "volume": 27681100,
      "marketCap": 483937892568,
      "quotedAt": "2026-09-06T17:24:54Z",
      "source": "brapi",
      "cached": true
    }
  },
  {
    "ticker": "ZZZZ9",
    "status": "notFound",
    "quote": null
  }
]
```

**Por que o item da lista envolve a cotação em vez de achatá-la.** Um ativo não
encontrado não tem preço, moeda nem instante — e `price` é campo obrigatório do
nosso contrato. Achatar obrigaria a torná-lo anulável, e todo consumidor passaria
a receber `Optional` para um campo que, quando existe cotação, sempre vem
preenchido. O envelope mantém `QuoteResponse` exatamente como está, reaproveitado
sem alteração entre as duas rotas.

`status` assume `found` ou `notFound`.

### Erros

Mesmo corpo de sempre (`ProblemDetail`). Os novos casos:

| Situação | `type` | HTTP |
|---|---|---|
| Nenhum ativo informado | `/errors/invalid-ticker` | `400` |
| Acima do limite | `/errors/too-many-tickers` | `400` |
| Cota da fonte esgotada | `/errors/provider-rate-limited` | `503` + `Retry-After` |

---

## 5. Formato do cache

Sem mudança de formato — chave `quote:v1:{TICKER}`, valor JSON do `Quote`, TTL
por ativo. O que muda é o **acesso**: `MGET` na leitura e pipeline na escrita
(ADR-011). As chaves gravadas pela Spec 001 continuam válidas.

---

## 6. Tradução: BRAPI → domínio

O mapeamento campo a campo é o mesmo da Spec 001. O que muda é o **percurso**:

| Antes | Agora |
|---|---|
| Lê `results[0]` | Percorre **todos** os itens de `results` |
| Devolve um `Quote` | Devolve `Mapping[Ticker, Quote]`, indexado pelo `symbol` de cada item |
| `results` vazio → não encontrado | Códigos ausentes do mapa → não encontrados |

Um item cujo `symbol` não passa na regra do `Ticker` — um índice, por exemplo —
é ignorado em vez de derrubar o lote: ele não foi pedido por nós, então não pode
estragar o resultado de quem foi.
