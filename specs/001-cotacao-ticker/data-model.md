# Modelo de dados — Spec 001

O MVP não tem banco. "Modelo de dados" aqui significa as estruturas do domínio,
o contrato de saída da nossa API e o formato do cache.

---

## 1. Domínio (`src/investimentos/domain/model/`)

### `Ticker` — Value Object

Encapsula o código de negociação e a regra RN-01. Existe para que seja
**impossível** um código inválido circular pelo sistema: se o objeto existe, ele
é válido.

| Atributo | Tipo | Regra |
|---|---|---|
| `value` | `str` | Normalizado para maiúsculas (RN-02); casa com `^[A-Z][A-Z0-9]{3}\d{1,2}F?$` (RN-01) |

- Imutável (`frozen=True`), comparável por valor, utilizável como chave de dict.
- Construção inválida levanta `InvalidTickerError`.
- Exemplos válidos: `PETR4`, `VALE3`, `B3SA3`, `BOVA11`, `MXRF11`, `AAPL34`, `PETR4F`.
- Exemplos inválidos: `PETR`, `PE4`, `PETR44444`, `PETR4X`, `1PET4`, `""`, `"; DROP"`.

O prefixo aceita dígito a partir do segundo caractere porque a B3 emite códigos
assim — `B3SA3` é o caso clássico, e os BDRs (`M1TA34`) também. A regra anterior,
de quatro letras, foi corrigida quando um teste com `B3SA3` a reprovou.

### `Quote` — Value Object

Snapshot imutável da cotação num instante. Não tem identidade própria: duas
cotações com os mesmos valores são a mesma cotação.

| Atributo | Tipo | Obrigatório | Observação |
|---|---|---|---|
| `ticker` | `Ticker` | sim | |
| `short_name` | `str` | sim | Nome curto do ativo |
| `long_name` | `str \| None` | não | Razão social, quando a fonte informa |
| `currency` | `str` | sim | ISO 4217, ex. `BRL` |
| `price` | `Decimal` | sim | Preço atual (RN-03) |
| `change` | `Decimal \| None` | não | Variação absoluta no dia |
| `change_percent` | `Decimal \| None` | não | Variação percentual no dia |
| `volume` | `int \| None` | não | Volume negociado |
| `market_cap` | `Decimal \| None` | não | Valor de mercado |
| `quoted_at` | `datetime` | sim | Instante informado pela fonte, em UTC (RN-04) |

**Invariantes verificadas na construção:**
- `price` não pode ser negativo.
- `quoted_at` precisa ter fuso horário definido (*timezone-aware*).
- `currency` precisa ter exatamente 3 caracteres.

Campos opcionais são opcionais porque a fonte externa nem sempre os devolve —
para ativos recém-listados ou fora do pregão. Tratá-los como obrigatórios
transformaria dado ausente em erro `502`, o que seria mentira.

### Hierarquia de exceções (`domain/exceptions.py`)

```
DomainError
├── InvalidTickerError            → 400
├── QuoteNotFoundError            → 404
└── QuoteProviderError            → família de falhas da fonte externa
    ├── QuoteProviderAuthError    → 502
    ├── QuoteProviderRateLimited  → 503
    ├── QuoteProviderTimeout      → 504
    └── QuoteProviderContractError→ 502
```

Nenhuma delas conhece HTTP. O mapeamento para status é responsabilidade
exclusiva do adapter de entrada (Artigo VIII).

---

## 2. Contrato de saída da nossa API

### `GET /cotacao/{ticker}` — `200 OK`

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
  "quotedAt": "2026-09-03T17:24:54Z",
  "source": "brapi",
  "cached": false
}
```

- `camelCase` na fronteira HTTP, `snake_case` no Python. A tradução é
  declarativa no schema, não manual.
- `source` e `cached` são metadados nossos, úteis para depurar. Não vêm da fonte.
- Este contrato é **nosso**. Se a BRAPI renomear um campo, muda o mapper —
  não muda esta resposta. É o ponto 2 do problema original resolvido.

### Corpo de erro — padronizado (RF-10)

Mesmo formato para todo status de erro, inspirado em RFC 9457:

```json
{
  "type": "https://projeto-investimentos/errors/invalid-ticker",
  "title": "Código de ativo inválido",
  "status": 400,
  "detail": "O código 'PETR' não segue o padrão da B3: quatro caracteres começando por letra, seguidos de um ou dois dígitos, com 'F' opcional.",
  "instance": "/cotacao/PETR"
}
```

Nenhum campo carrega *stack trace*, detalhe interno ou qualquer parte da
credencial (Artigo V).

### `GET /` — índice

```json
{
  "servico": "Projeto Investimentos API",
  "versao": "1.0.0",
  "status": "ok",
  "exemplo": "http://localhost:8000/cotacao/PETR4",
  "rotas": {
    "cotacao": "/cotacao/{ticker}",
    "saude": "/health",
    "openapi": "/openapi.json",
    "documentacao": "/docs"
  }
}
```

Existe para que abrir `localhost:8000` no navegador responda a pergunta "e
agora, como eu uso isso?" — em JSON, sem tela e sem botão.

### `GET /health`

```json
{
  "status": "ok",
  "dependencies": { "cache": "ok" }
}
```

`status` é `ok` ou `degraded`. Cache fora do ar deixa o serviço `degraded`, com
`dependencies.cache` em `unavailable` — mas ainda `200`, porque cotação continua
funcionando (RF-06, CA-02.2). Só a indisponibilidade do próprio processo
justificaria falhar o healthcheck.

---

## 3. Formato do cache

| Item | Definição |
|---|---|
| Chave | `quote:v1:{TICKER}` |
| Valor | JSON do `Quote` serializado, com `Decimal` como string para não perder precisão |
| TTL | `CACHE_TTL_SECONDS`, padrão `60` |
| Codificação | UTF-8 |

Exemplo de valor armazenado:

```json
{
  "ticker": "PETR4",
  "short_name": "PETR4",
  "long_name": "Petroleo Brasileiro SA Petrobras",
  "currency": "BRL",
  "price": "36.65",
  "change": "-0.35",
  "change_percent": "-0.95",
  "volume": 27681100,
  "market_cap": "483937892568",
  "quoted_at": "2026-09-03T17:24:54+00:00"
}
```

`Decimal` vai como **string** de propósito: serializar como número JSON o
converteria para float na volta e devolveria o erro binário que a ADR-003
eliminou.

---

## 4. Tradução: BRAPI → domínio

Feita exclusivamente em `adapters/outbound/brapi/mapper.py`.

| Campo da fonte | Campo do domínio | Transformação |
|---|---|---|
| `symbol` | `ticker` | Constrói `Ticker` (revalida) |
| `shortName` | `short_name` | Direto |
| `longName` | `long_name` | Direto, opcional |
| `currency` | `currency` | Direto, com padrão `BRL` |
| `regularMarketPrice` | `price` | `Decimal(str(v))` |
| `regularMarketChange` | `change` | `Decimal(str(v))`, opcional |
| `regularMarketChangePercent` | `change_percent` | `Decimal(str(v))`, opcional |
| `regularMarketVolume` | `volume` | `int`, opcional |
| `marketCap` | `market_cap` | `Decimal(str(v))`, opcional |
| `regularMarketTime` | `quoted_at` | ISO 8601 → `datetime` UTC; ausente vira `now(UTC)` |

O item bruto é normalizado antes do mapeamento: os campos do nível externo e os
de `data` são **mesclados**, com `data` vencendo em caso de conflito. Isso
absorve as duas gerações de resposta da BRAPI (ADR-004) e preserva o `symbol`,
que no v2 fica fora de `data`.

Ausência de `regularMarketPrice`, ou payload que não é um objeto, levanta
`QuoteProviderContractError` — nunca produz um `Quote` com preço zero.
