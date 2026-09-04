# Plano de Implementação — Spec 001

- **Spec de origem:** `specs/001-cotacao-ticker/spec.md`
- **Clarificação:** `specs/001-cotacao-ticker/clarify.md`
- **Decisões técnicas:** `specs/001-cotacao-ticker/research.md`
- **Constituição:** v1.0.0
- **Data:** 2026-09-03

---

## 1. Portão constitucional (pré-implementação)

| Artigo | Verificação | Situação | Evidência |
|---|---|---|---|
| I — Spec antes do código | Spec aprovada, sem `[NEEDS CLARIFICATION]` | ✅ | `spec.md` §9, `clarify.md` Q1–Q8 |
| II — Hexagonal | Dependência aponta só para dentro | ✅ | §3 e §4 deste plano; teste de arquitetura T-ARCH |
| III — SOLID | Portas pequenas, DIP no caso de uso | ✅ | §4; caso de uso recebe portas por construtor |
| IV — Teste antes | Todo RF com teste planejado | ✅ | §8 rastreabilidade |
| V — Segredos | Nada versionado, token só em header | ✅ | `.gitignore`, `.env.example`, ADR-004 |
| VI — Docker | Sobe com um comando | ✅ | §6 |
| VII — Simplicidade | Abstração especulativa registrada | ✅ | §7 Complexity Tracking |
| VIII — Erros | Todo erro mapeado para status | ✅ | §5 |
| IX — Observabilidade | Log de chamada externa e `/health` | ✅ | RF-07, RNF-07 |

Portão **verde**. Implementação liberada.

---

## 2. Stack e versões

| Camada | Escolha | Versão | Decisão |
|---|---|---|---|
| Linguagem | Python | 3.12 | Imagem base `python:3.12-slim` |
| Borda HTTP | FastAPI + Uvicorn | 0.115.x / 0.32.x | Q2 |
| Validação e schemas | Pydantic + pydantic-settings | 2.9.x / 2.6.x | Q2 |
| Cliente HTTP | httpx | 0.27.x | ADR-001 |
| Cache | redis (asyncio) | 5.2.x | Q3, ADR-005 |
| Testes | pytest, pytest-asyncio, respx | 8.3.x / 0.24.x / 0.21.x | Q6 |
| Lint e formato | ruff | 0.7.x | CI |
| Tipos | mypy | 1.13.x | ADR-002 |
| Dependências | pip + requirements.txt | — | Q5 |

Versões fixadas com `==`. Sem lockfile por decisão consciente (Q5).

---

## 3. Estrutura de diretórios

```
projeto-investimentos/
├── .specify/
│   ├── memory/constitution.md          ← governança
│   └── templates/                      ← moldes das próximas specs
├── specs/001-cotacao-ticker/           ← esta feature
│   ├── spec.md  clarify.md  plan.md
│   ├── research.md  data-model.md  quickstart.md  tasks.md
│   └── contracts/
│       ├── openapi.yaml                ← contrato que NÓS publicamos
│       └── brapi-quote.md              ← contrato que NÓS consumimos
├── src/investimentos/
│   ├── domain/                         ── NÚCLEO: só stdlib
│   │   ├── model/ticker.py             VO Ticker  (RN-01, RN-02)
│   │   ├── model/quote.py              VO Quote   (RN-03, RN-04)
│   │   └── exceptions.py               hierarquia de erro de domínio
│   ├── application/                    ── CASOS DE USO: só domain
│   │   ├── ports/quote_provider.py     porta de saída (Protocol)
│   │   ├── ports/quote_cache.py        porta de saída (Protocol)
│   │   └── usecases/get_quote.py       orquestração cache → fonte → cache
│   ├── adapters/                       ── BORDA: conhece infraestrutura
│   │   ├── inbound/http/
│   │   │   ├── app.py                  factory do FastAPI + lifespan
│   │   │   ├── dependencies.py         ponte FastAPI Depends → container
│   │   │   ├── schemas.py              DTOs de entrada e saída (camelCase)
│   │   │   ├── error_handlers.py       exceção de domínio → status HTTP
│   │   │   └── routers/cotacao.py, health.py, root.py
│   │   └── outbound/
│   │       ├── brapi/client.py         httpx + auth + timeout + tradução de erro
│   │       ├── brapi/mapper.py         JSON da BRAPI → Quote
│   │       ├── cache/redis_cache.py    implementação real
│   │       └── cache/null_cache.py     implementação degradada
│   ├── config/settings.py              variáveis de ambiente (pydantic-settings)
│   ├── config/container.py             COMPOSITION ROOT — único lugar que monta
│   ├── config/logging.py               log estruturado
│   └── main.py                         ponto de entrada
├── tests/
│   ├── unit/domain/  unit/application/ sem I/O
│   ├── integration/                    rota ponta a ponta, BRAPI mockada
│   ├── contract/                       BRAPI real, opt-in
│   └── test_architecture.py            valida o Artigo II automaticamente
├── Dockerfile  docker-compose.yml  .dockerignore
├── .env.example  .gitignore  README.md
├── requirements.txt  requirements-dev.txt  pyproject.toml
└── .github/workflows/ci.yml
```

**A regra de ouro, legível na árvore:** `domain/` não importa nada.
`application/` importa `domain/`. `adapters/` importa os dois. Nunca o inverso.
Isso não é convenção verbal — `tests/test_architecture.py` falha o build se for
violado.

---

## 4. Portas e adapters

| Porta | Direção | Assinatura | Implementações |
|---|---|---|---|
| `QuoteProviderPort` | saída (driven) | `async fetch(ticker: Ticker) -> Quote` | `BrapiQuoteProvider` · dublês nos testes |
| `QuoteCachePort` | saída (driven) | `async get(ticker) -> Quote \| None`<br>`async set(ticker, quote) -> None`<br>`async ping() -> bool` | `RedisQuoteCache` · `NullQuoteCache` |

O adapter de **entrada** (HTTP) não tem porta formal: no hexágono, a porta de
entrada é a própria interface pública do caso de uso. `GetQuoteUseCase.execute`
é essa porta.

**Composition root.** `config/container.py` é o único módulo que instancia
adapters concretos. Ele decide, a partir das settings, se o cache é Redis ou
Null. Nem o caso de uso nem a rota sabem qual é qual — LSP do Artigo III.

---

## 5. Fluxo de uma requisição e mapeamento de erros

```
GET /cotacao/petr4
      │
      ▼  adapters/inbound/http/routers/cotacao.py
  ① Ticker("petr4") ─── normaliza p/ PETR4, valida RN-01
      │                  inválido → InvalidTickerError → 400 (sem chamada externa)
      ▼  application/usecases/get_quote.py
  ② cache.get(PETR4) ── hit  → devolve com "cached": true  ─────────────┐
      │                                                                 │
      ▼ miss                                                            │
  ③ provider.fetch(PETR4) ── adapters/outbound/brapi/client.py          │
      │   GET /api/v2/stocks/quote?symbols=PETR4                        │
      │   Authorization: Bearer ***  (nunca em log)                     │
      │   timeout configurável                                          │
      ▼                                                                 │
  ④ mapper: JSON → Quote (Decimal via str, UTC, mescla raiz + "data")   │
      │                                                                 │
      ▼                                                                 │
  ⑤ cache.set(PETR4, quote, ttl)   falha aqui só gera warning           │
      │                                                                 │
      ▼  ◄──────────────────────────────────────────────────────────────┘
  ⑥ Quote → QuoteResponse (camelCase) → 200
```

**Mapeamento de erros (Artigo VIII):**

| Exceção de domínio | HTTP | Quando |
|---|---|---|
| `InvalidTickerError` | `400` | Formato fora da RN-01 |
| `QuoteNotFoundError` | `404` | Fonte respondeu, ativo não existe |
| `QuoteProviderAuthError` | `502` | Fonte rejeitou a credencial |
| `QuoteProviderRateLimited` | `503` | Cota da fonte esgotada |
| `QuoteProviderTimeout` | `504` | Estourou o timeout configurado |
| `QuoteProviderContractError` | `502` | Payload da fonte fora do esperado |
| Qualquer outra | `500` | Handler genérico; loga, não vaza detalhe |

Todos produzem o mesmo corpo (`data-model.md` §2).

---

## 6. Docker (Artigo VI)

Dois serviços no compose:

| Serviço | Imagem | Porta | Healthcheck | Depende de |
|---|---|---|---|---|
| `api` | build local, multi-stage, não-root | `8000:8000` | `GET /health` via Python puro | `redis` saudável |
| `redis` | `redis:7-alpine` | interna | `redis-cli ping` | — |

Subida completa: `docker compose up -d` → abrir `http://localhost:8000` →
redirect para o Swagger UI → executar a rota. Nenhum passo manual entre eles.

O `.env` é lido pelo compose. Sem `.env`, o serviço ainda sobe e atende os
tickers de sandbox (`PETR4`, `VALE3`, `MGLU3`, `ITUB4`), que dispensam token.

---

## 7. Complexity Tracking (Artigo VII)

| Complexidade | Por que é necessária | Alternativa mais simples e por que não serve |
|---|---|---|
| Duas implementações de `QuoteCachePort` | RF-06 exige atender cotação com o cache fora do ar | Um `try/except` em volta do Redis dentro do caso de uso — poluiria a camada de aplicação com detalhe de infraestrutura, violando o Artigo II |
| `BRAPI_QUOTE_PATH` configurável + mapper que mescla raiz e `data` | Absorveu a migração para o endpoint v2 sem tocar em código quando a geração ativa foi confirmada (ADR-004) | Fixar um formato — teria exigido alteração de código no momento da confirmação |
| Campo `cached` na resposta | Torna o RF-05 observável de fora e testável sem inspecionar o Redis | Só log — não seria verificável pelo teste de integração |

Nada além disso foi adicionado "para o futuro".

---

## 8. Rastreabilidade requisito → projeto → teste

| Req. | Onde é implementado | Teste que falha se violado |
|---|---|---|
| RF-01 | `routers/cotacao.py` + `usecases/get_quote.py` | `integration/test_cotacao_route.py::test_retorna_cotacao` |
| RF-02 | `domain/model/ticker.py` | `unit/domain/test_ticker.py::test_rejeita_formato_invalido` |
| RF-03 | `domain/model/ticker.py` | `unit/domain/test_ticker.py::test_normaliza_para_maiusculas` |
| RF-04 | `adapters/outbound/brapi/mapper.py` | `unit/adapters/test_mapper.py` |
| RF-05 | `usecases/get_quote.py` + `redis_cache.py` | `unit/application/test_get_quote.py::test_cache_hit_nao_chama_a_fonte` |
| RF-06 | `null_cache.py` + tratamento no `redis_cache.py` | `unit/application/test_get_quote.py::test_cache_indisponivel` |
| RF-07 | `routers/health.py` | `integration/test_health.py` |
| RF-08 | `routers/root.py` | `integration/test_root_index.py` |
| RF-09 | `app.py` (FastAPI) | `integration/test_openapi.py` |
| RF-10 | `error_handlers.py` | `integration/test_error_contract.py` |
| RNF-02 | `.gitignore`, `settings.py`, `client.py` | `unit/test_no_secret_leak.py` |
| RNF-05 | estrutura de `domain/` | `test_architecture.py` |
| Artigo II | toda a árvore | `test_architecture.py` |

---

## 9. Riscos

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| ~~Formato de resposta da BRAPI diferente do previsto~~ | — | — | **Resolvido**: endpoint v2 confirmado com payload real (ADR-004) |
| A BRAPI mudar de geração de novo | Baixa | Médio | Path configurável por ambiente; mapper aceita as duas gerações; contract test detecta |
| Cota gratuita da BRAPI esgotar durante o desenvolvimento | Média | Médio | Cache de 60s; testes rodam mockados; sandbox sem token |
| Exposição do serviço fora da rede local sem autenticação | Baixa hoje | Alto | Q7 registrou a condição de reabertura: revisar antes de qualquer deploy externo |
| Token commitado por engano | Baixa | Crítico | `.gitignore` antes do primeiro commit; `.env.example` sem valor real; se ocorrer, **rotacionar o token** (Artigo V) |
