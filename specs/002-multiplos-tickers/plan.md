# Implementation Plan: Consulta de múltiplos tickers com cache por ativo

**Branch**: `002-multiplos-tickers` | **Date**: 2026-09-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-multiplos-tickers/spec.md`

## Summary

Substituir a rota `/cotacao/{ticker}` por duas: `GET /ticker/{codigo}`, que
devolve um objeto, e `GET /ticker`, que recebe o parâmetro `ticker` repetido e
devolve uma lista.

A abordagem técnica gira em torno de uma inversão simples: hoje o caso de uso
pergunta ao cache por **um** ativo; passa a perguntar por **vários de uma vez** e
a chamar a fonte externa **uma única vez**, apenas com os que faltaram. As portas
deixam de ter operação singular — `fetch_many`, `get_many` e `set_many`
substituem as versões de um item, e a consulta individual passa a ser o caso
particular de uma lista de um elemento.

## Technical Context

**Language/Version**: Python 3.12 (imagem `python:3.12-slim`); a suíte também roda em 3.10

**Primary Dependencies**: FastAPI 0.115, Pydantic 2.10, httpx 0.27, redis 5.2

**Storage**: Redis como cache com TTL. Sem banco relacional — segue fora de escopo desde a Spec 001

**Testing**: pytest 8.3 com pytest-asyncio e respx; contract test opt-in contra a BRAPI real

**Target Platform**: contêiner Linux, subido por `docker compose up -d`

**Project Type**: serviço web (API HTTP), arquitetura hexagonal

**Performance Goals**: uma consulta de N ativos faz no máximo 1 chamada externa e no máximo 1 ida ao Redis por operação (leitura em lote, escrita em lote)

**Constraints**: no máximo 3 ativos por requisição no padrão — teto do plano gratuito da fonte, configurável; timeout de 8s na chamada externa; a suíte roda offline

**Scale/Scope**: uso pessoal. O gargalo real não é carga, é **cota**: 
o plano gratuito da fonte é o recurso escasso que esta feature existe para poupar

## Constitution Check

*GATE: passar antes da Fase 0. Reavaliado após a Fase 1.* Constituição v1.1.0.

| Artigo | Verificação | Situação |
|---|---|---|
| I — Spec antes do código | Spec aprovada, clarificada, sem marcador em aberto | ✅ |
| II — Hexagonal | Dependência aponta só para dentro; FastAPI só na borda | ✅ |
| III — SOLID | Portas continuam pequenas; a plural substitui a singular em vez de somar | ✅ |
| IV — Teste antes | Todo FR com teste planejado (§8) | ✅ |
| V — Segredos | Nada muda no tratamento do token | ✅ |
| VI — Docker | Uma variável nova, com padrão; sobe igual | ✅ |
| VII — Simplicidade | Sem fatiamento de lote — ver Complexity Tracking | ✅ |
| VIII — Erro é contrato | Falha parcial mapeada; corpo de erro inalterado | ✅ |
| IX — Observabilidade | Log passa a registrar quantos vieram do cache e quantos da fonte | ✅ |
| **X — DDD** | Linguagem ubíqua (`ticker`, não `symbols`); `Quote` continua Value Object puro; metadado de origem fica na aplicação, não no domínio | ✅ |
| **XI — Design de API** | Item devolve objeto, coleção devolve lista sempre; filtro em query; quebra registrada no FR-017 | ✅ |

Portão **verde**. Implementação liberada.

## Project Structure

### Documentation (this feature)

```text
specs/002-multiplos-tickers/
├── spec.md              # O quê e por quê, com a sessão de clarificação
├── plan.md              # Este arquivo
├── research.md          # Fase 0 — decisões técnicas desta feature
├── data-model.md        # Fase 1 — estruturas e contratos
├── quickstart.md        # Fase 1 — roteiro de validação manual
├── contracts/
│   └── openapi.yaml     # Fase 1 — o contrato que passamos a publicar
├── checklists/
│   └── requirements.md  # /speckit-checklist
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

Serviço único, hexagonal. **Nenhum diretório novo** — a feature muda arquivos
que já existem e acrescenta dois.

```text
src/investimentos/
├── domain/
│   ├── model/ticker.py            (inalterado)
│   ├── model/quote.py             (inalterado — Value Object puro, Artigo X)
│   └── exceptions.py              + TooManyTickersError
├── application/
│   ├── ports/quote_provider.py    fetch → fetch_many
│   ├── ports/quote_cache.py       get/set → get_many/set_many
│   └── usecases/get_quote.py      GetQuotesUseCase + QuoteLookup/QuoteResolution
├── adapters/
│   ├── inbound/http/
│   │   ├── routers/ticker.py      NOVO — as duas rotas (substitui cotacao.py)
│   │   ├── routers/root.py        índice anuncia as rotas novas
│   │   ├── schemas.py             + TickerLookupItem, status por ativo
│   │   └── error_handlers.py      + TooManyTickersError → 400
│   └── outbound/
│       ├── brapi/client.py        1 chamada com códigos separados por vírgula
│       ├── brapi/mapper.py        extrai todos os itens, não só o primeiro
│       └── cache/redis_cache.py   MGET e pipeline
└── config/settings.py             + max_tickers_per_request

tests/
├── unit/                          domínio, caso de uso, mapper, cliente, cache
├── integration/                   as duas rotas, contrato de erro, OpenAPI
└── contract/                      consulta múltipla real (opt-in)
```

## Design

### 1. Portas: a plural substitui a singular

O Artigo III (ISP) pede portas pequenas, e o VII proíbe manter duas formas de
fazer a mesma coisa. Então a operação de um item **não coexiste** com a de
vários: ela deixa de existir, e a consulta individual vira o caso de uma lista
de um elemento.

| Porta | Antes | Depois |
|---|---|---|
| `QuoteProviderPort` | `fetch(ticker) -> Quote` | `fetch_many(tickers) -> Mapping[Ticker, Quote]` |
| `QuoteCachePort` | `get(ticker)` / `set(ticker, quote)` | `get_many(tickers)` / `set_many(quotes)` |

`fetch_many` devolve **apenas os encontrados**. Ausência no mapa significa "a
fonte não conhece este ativo" — o que dá ao chamador a informação do FR-011 sem
inventar exceção por item.

### 2. O caso de uso

```
GET /ticker?ticker=itsa4&ticker=petr4
      │
      ▼  ① valida e normaliza cada código  (domínio)
         inválido → InvalidTickerError → 400, sem chamada externa
         acima do limite → TooManyTickersError → 400
         duplicados removidos, ordem original preservada
      │
      ▼  ② cache.get_many(todos)          → 1 ida ao Redis (MGET)
      │
      ├── faltantes vazio ────────────────────────────┐
      │                                               │
      ▼  ③ provider.fetch_many(faltantes) → 1 chamada │
      │      GET /api/v2/stocks/quote?symbols=A,B     │
      │                                               │
      ▼  ④ cache.set_many(obtidos)        → 1 pipeline│
      │                                               │
      ▼  ◄────────────────────────────────────────────┘
         ⑤ monta QuoteLookup na ordem pedida, cada item com origem
```

Quando todos estão em cache, o passo ③ **não acontece** — é o SC-002, e o teste
o verifica contando chamadas ao dublê.

### 3. Modelo (Artigo X)

`Quote` continua Value Object puro, sem saber de cache. Os tipos de resultado
vivem em `application/`, porque origem e status são desfecho de orquestração,
não conceito de negócio:

- `QuoteResolution` — um ativo pedido e o que aconteceu com ele: `ticker`,
  `quote | None`, `origin` (`CACHE` | `SOURCE`), `status` (`FOUND` | `NOT_FOUND`).
- `QuoteLookup` — a coleção ordenada de resoluções, com atalhos de leitura
  (`found`, `not_found`) para a borda montar a resposta sem lógica própria.

### 4. Mapeamento de erros

| Situação | Exceção | HTTP |
|---|---|---|
| Qualquer código com formato inválido | `InvalidTickerError` | `400` |
| Nenhum código informado | `InvalidTickerError` | `400` |
| Acima do limite configurado | `TooManyTickersError` | `400` |
| Código válido que a bolsa não conhece, em `/ticker` | — | `200`, item com `status: notFound` |
| Código válido que a bolsa não conhece, em `/ticker/{codigo}` | `QuoteNotFoundError` | `404` |
| Cota da fonte esgotada | `QuoteProviderRateLimitedError` | `503` + header `Retry-After` |

A assimetria entre as duas últimas linhas é deliberada e vem do Artigo XI: numa
coleção, "não encontrado" é um resultado; num item, é a ausência do recurso.

## Complexity Tracking

| Violação | Por que é necessária | Alternativa mais simples rejeitada porque |
|---|---|---|
| Nenhuma | — | — |

**O que foi deliberadamente NÃO construído**, por força do Artigo VII:

- **Fatiamento do lote.** Como o nosso limite (3) é menor ou igual ao da fonte,
  uma chamada sempre basta. Fatiar seria código para um cenário que a
  configuração impede. Fica registrado que `MAX_TICKERS_PER_REQUEST` **não pode**
  ser elevado acima do limite do plano sem antes implementar o fatiamento — o
  teste `test_limite_nao_excede_o_da_fonte` guarda essa condição.
- **Repetição automática em 429.** O FR-013 pede respeitar a sinalização da
  fonte, não insistir sozinho. Um retry dentro da requisição prenderia o cliente
  por segundos sem que ele pedisse. Em vez disso, o `Retry-After` da fonte é
  repassado no nosso `503` — quem chamou decide se espera.
- **Rota antiga como apelido.** O FR-017 manda remover, não depreciar.

## Rastreabilidade requisito → projeto → teste

| Req. | Onde | Teste que falha se violado |
|---|---|---|
| FR-001 | `routers/ticker.py` | `integration/test_ticker_lista.py::test_consulta_tres_ativos` |
| FR-002 | `domain/model/ticker.py` | `integration/test_ticker_lista.py::test_formato_invalido_nao_chama_a_fonte` |
| FR-003 | `usecases/get_quote.py` | `unit/application/test_get_quotes.py::test_normaliza_e_deduplica` |
| FR-004 | `usecases/get_quote.py` | `unit/application/test_get_quotes.py::test_consulta_o_cache_por_ativo` |
| FR-005 | `usecases/get_quote.py` | `unit/application/test_get_quotes.py::test_so_os_faltantes_vao_a_fonte` |
| FR-006 | `usecases/get_quote.py` | `unit/application/test_get_quotes.py::test_uma_chamada_so` |
| FR-007 | `usecases/get_quote.py` | `unit/application/test_get_quotes.py::test_tudo_em_cache_nao_chama_a_fonte` |
| FR-008 | `redis_cache.py` | `unit/adapters/test_redis_cache.py::test_set_many` |
| FR-009 | `schemas.py` | `integration/test_ticker_lista.py::test_marca_origem_por_ativo` |
| FR-010 | `settings.py`, `usecases` | `integration/test_ticker_lista.py::test_acima_do_limite` |
| FR-011 | `usecases`, `error_handlers.py` | `integration/test_ticker_lista.py::test_falha_parcial` |
| FR-012 | `routers/ticker.py` | `integration/test_ticker_item.py`, `test_ticker_lista.py` |
| FR-013 | `brapi/client.py` | `unit/adapters/test_brapi_client.py::test_retry_after` |
| FR-014 | `redis_cache.py` | `unit/application/test_get_quotes.py::test_cache_indisponivel` |
| FR-015 | `schemas.py` | `integration/test_openapi.py` |
| FR-016 | `usecases/get_quote.py` | `unit/application/test_get_quotes.py::test_preserva_a_ordem` |
| FR-017 | `app.py` | `integration/test_ticker_item.py::test_rota_antiga_sumiu` |
| Artigo X | toda a árvore | `test_architecture.py` |
| Artigo XI | `contracts/openapi.yaml` | `integration/test_openapi.py` |

## Riscos

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| O plano gratuito aceitar menos de 3 ativos por chamada | Média | Médio | Limite configurável; o contract test revela o teto real |
| A fonte devolver menos itens do que os pedidos, sem avisar | Média | Médio | O mapper trabalha por código pedido, não por posição; ausente vira `notFound` |
| `MAX_TICKERS_PER_REQUEST` ser elevado acima do teto do plano | Baixa | Alto | Registrado no Complexity Tracking; teste guarda a condição |
| Quebra de contrato para consumidores da rota antiga | Nenhuma hoje | — | Só o autor consome; registrado no FR-017 |
