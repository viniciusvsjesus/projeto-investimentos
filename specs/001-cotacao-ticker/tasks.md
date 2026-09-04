# Tarefas — Spec 001

- **Plano de origem:** `specs/001-cotacao-ticker/plan.md`
- **Constituição:** v1.0.0

## Convenções

- `[P]` — pode ser executada em paralelo com outras `[P]` do mesmo bloco (arquivos distintos).
- Toda tarefa `impl` é precedida pela sua tarefa `test` (Artigo IV): escreve o teste, vê falhar, implementa, vê passar.
- Uma tarefa só fecha com o teste correspondente verde.

---

## Bloco 0 — Fundação do repositório

| # | Tarefa | Arquivo | Status |
|---|---|---|---|
| T000 | `.gitignore` cobrindo `.env`, caches, virtualenv e artefatos de credencial — **antes de qualquer commit** | `.gitignore` | ✅ |
| T001 | `.env.example` com placeholders, zero valor real | `.env.example` | ✅ |
| T002 | `requirements.txt` e `requirements-dev.txt` com versões fixas | — | ✅ |
| T003 | `pyproject.toml`: `pythonpath=src`, marcador `contract`, ruff, mypy | `pyproject.toml` | ✅ |
| T004 | Pacotes `__init__.py` da árvore `src/` | — | ✅ |

> T000 é a primeira tarefa do projeto por decisão do Artigo V: `.gitignore`
> depois do primeiro commit é tarde demais.

## Bloco 1 — Domínio (Artigo II: só stdlib)

| # | Tarefa | Arquivo | Requisito | Status |
|---|---|---|---|---|
| T010 | **test** `[P]` Ticker: normaliza, valida, rejeita, é imutável e hashável | `tests/unit/domain/test_ticker.py` | RF-02, RF-03, RN-01, RN-02 | ✅ |
| T011 | **test** `[P]` Quote: invariantes de preço, moeda e timezone | `tests/unit/domain/test_quote.py` | RN-03, RN-04 | ✅ |
| T012 | **impl** Value Object `Ticker` | `domain/model/ticker.py` | RF-02, RF-03 | ✅ |
| T013 | **impl** Value Object `Quote` | `domain/model/quote.py` | RN-03, RN-04 | ✅ |
| T014 | **impl** Hierarquia de exceções de domínio | `domain/exceptions.py` | Artigo VIII | ✅ |

## Bloco 2 — Aplicação (Artigo II: só domain)

| # | Tarefa | Arquivo | Requisito | Status |
|---|---|---|---|---|
| T020 | **impl** `[P]` Porta `QuoteProviderPort` | `application/ports/quote_provider.py` | Artigo III (DIP) | ✅ |
| T021 | **impl** `[P]` Porta `QuoteCachePort` | `application/ports/quote_cache.py` | Artigo III (DIP) | ✅ |
| T022 | **test** Caso de uso: cache hit não chama a fonte | `tests/unit/application/test_get_quote.py` | RF-05 | ✅ |
| T023 | **test** Caso de uso: cache miss chama a fonte e grava | idem | RF-05 | ✅ |
| T024 | **test** Caso de uso: cache indisponível não impede a resposta | idem | RF-06 | ✅ |
| T025 | **test** Caso de uso: falha ao gravar no cache não derruba a resposta | idem | RF-06 | ✅ |
| T026 | **impl** `GetQuoteUseCase` | `application/usecases/get_quote.py` | RF-01, RF-05, RF-06 | ✅ |

## Bloco 3 — Adapters de saída

| # | Tarefa | Arquivo | Requisito | Status |
|---|---|---|---|---|
| T030 | **test** `[P]` Mapper: as duas gerações da BRAPI, o payload real do v2, campos ausentes, payload inválido | `tests/unit/adapters/test_brapi_mapper.py` | RF-04, ADR-004 | ✅ |
| T031 | **impl** Mapper JSON → `Quote` | `adapters/outbound/brapi/mapper.py` | RF-04 | ✅ |
| T032 | **test** Cliente BRAPI: cada status vira a exceção certa | `tests/unit/adapters/test_brapi_client.py` | Artigo VIII | ✅ |
| T033 | **impl** `BrapiQuoteProvider` com httpx, Bearer e timeout | `adapters/outbound/brapi/client.py` | RF-01, RNF-04 | ✅ |
| T034 | **impl** `[P]` `NullQuoteCache` | `adapters/outbound/cache/null_cache.py` | RF-06 | ✅ |
| T035 | **impl** `[P]` `RedisQuoteCache` com degradação silenciosa | `adapters/outbound/cache/redis_cache.py` | RF-05, RF-06 | ✅ |

## Bloco 4 — Configuração e composition root

| # | Tarefa | Arquivo | Requisito | Status |
|---|---|---|---|---|
| T040 | **impl** `Settings` via pydantic-settings, token como `SecretStr` | `config/settings.py` | RNF-02, RNF-08 | ✅ |
| T041 | **impl** Log estruturado com nível configurável | `config/logging.py` | RNF-07, Artigo IX | ✅ |
| T042 | **impl** Container — único lugar que instancia adapters | `config/container.py` | Artigo II | ✅ |

## Bloco 5 — Adapter de entrada (HTTP)

| # | Tarefa | Arquivo | Requisito | Status |
|---|---|---|---|---|
| T050 | **impl** `[P]` Schemas de resposta em camelCase | `adapters/inbound/http/schemas.py` | RF-04 | ✅ |
| T051 | **impl** `[P]` Handlers: exceção de domínio → status + ProblemDetail | `adapters/inbound/http/error_handlers.py` | RF-10, Artigo VIII | ✅ |
| T052 | **impl** Ponte `Depends` → container | `adapters/inbound/http/dependencies.py` | Artigo II | ✅ |
| T053 | **impl** Rota `GET /cotacao/{ticker}` | `adapters/inbound/http/routers/cotacao.py` | RF-01 | ✅ |
| T054 | **impl** `[P]` Rota de saúde | `adapters/inbound/http/routers/health.py` | RF-07 | ✅ |
| T055 | **impl** `[P]` Índice JSON na raiz | `adapters/inbound/http/routers/root.py` | RF-08 | ✅ |
| T056 | **impl** Factory da app + `lifespan` (ciclo de vida do httpx e do Redis) | `adapters/inbound/http/app.py` | RF-09, ADR-001 | ✅ |
| T057 | **impl** Ponto de entrada | `main.py` | — | ✅ |

## Bloco 6 — Testes de integração e de arquitetura

| # | Tarefa | Arquivo | Requisito | Status |
|---|---|---|---|---|
| T060 | **test** Rota de cotação ponta a ponta, BRAPI mockada por `respx` | `tests/integration/test_cotacao_route.py` | RF-01…RF-05 | ✅ |
| T061 | **test** `[P]` Corpo de erro padronizado em todos os status | `tests/integration/test_error_contract.py` | RF-10 | ✅ |
| T062 | **test** `[P]` Índice JSON da raiz | `tests/integration/test_root_index.py` | RF-08 | ✅ |
| T063 | **test** `[P]` Saúde nos dois estados | `tests/integration/test_health.py` | RF-07 | ✅ |
| T064 | **test** `[P]` OpenAPI publicado bate com `contracts/openapi.yaml` | `tests/integration/test_openapi.py` | RF-09 | ✅ |
| T065 | **test** Artigo II verificado por AST: nenhum import proibido | `tests/test_architecture.py` | RNF-05, Artigo II | ✅ |
| T066 | **test** `[P]` Token não vaza em `repr`, log ou resposta | `tests/unit/test_no_secret_leak.py` | RNF-02 | ✅ |

## Bloco 7 — Contract test (opt-in)

| # | Tarefa | Arquivo | Requisito | Status |
|---|---|---|---|---|
| T070 | **test** BRAPI real: payload, mapper e ticker inexistente | `tests/contract/test_brapi_contract.py` | ADR-004 | ✅ |

## Bloco 9 — Migração para o endpoint v2 (após confirmação do autor)

| # | Tarefa | Arquivo | Requisito | Status |
|---|---|---|---|---|
| T090 | **test** Fixture com o payload real do painel da BRAPI | `tests/conftest.py` | ADR-004 | ✅ |
| T091 | **impl** Mapper mescla raiz e `data` (o `symbol` do v2 fica na raiz) | `adapters/outbound/brapi/mapper.py` | RF-04 | ✅ |
| T092 | **impl** `BRAPI_QUOTE_PATH` passa a ter o v2 como padrão | `config/settings.py`, `.env.example` | ADR-004 | ✅ |
| T093 | **test** Corrigir RN-01: `B3SA3` e BDRs têm dígito no prefixo | `domain/model/ticker.py` | RN-01 | ✅ |
| T094 | **impl** Rota renomeada para `/cotacao/{ticker}` | `routers/cotacao.py` | RF-01 | ✅ |
| T095 | **impl** Raiz devolve índice JSON no lugar do redirect | `routers/root.py`, `schemas.py` | RF-08 | ✅ |

> T093 nasceu de um teste que falhou: o payload real usava `B3SA3`, e a regra
> original de "quatro letras" reprovava um código legítimo da própria B3.

## Bloco 8 — Empacotamento e entrega

| # | Tarefa | Arquivo | Requisito | Status |
|---|---|---|---|---|
| T080 | **impl** Dockerfile multi-stage, não-root, healthcheck | `Dockerfile` | Artigo VI | ✅ |
| T081 | **impl** `[P]` `.dockerignore` | `.dockerignore` | — | ✅ |
| T082 | **impl** `docker-compose.yml` com api + redis e healthchecks | `docker-compose.yml` | RNF-01 | ✅ |
| T083 | **impl** `[P]` README com instalação, uso e política de segredos | `README.md` | RNF-02 | ✅ |
| T084 | **impl** `[P]` CI: ruff + mypy + pytest sem os contract tests | `.github/workflows/ci.yml` | Artigo IV | ✅ |

---

## Ordem de execução

```
Bloco 0  →  Bloco 1  →  Bloco 2  →  Bloco 3  →  Bloco 4  →  Bloco 5  →  Bloco 6  →  Bloco 8
                                                                          │
                                                              Bloco 7 (independente, opt-in)
```

Blocos 3 e 4 só dependem de 1 e 2 — as portas já existem. Bloco 7 pode ser
executado a qualquer momento depois do Bloco 3, desde que haja token.

## Rastreabilidade consolidada

| Requisito | Tarefas | Teste que o prova |
|---|---|---|
| RF-01 | T026, T033, T053 | T060 |
| RF-02 | T012 | T010 |
| RF-03 | T012 | T010 |
| RF-04 | T031, T050 | T030 |
| RF-05 | T026, T035 | T022, T023, T060 |
| RF-06 | T026, T034, T035 | T024, T025 |
| RF-07 | T054 | T063 |
| RF-08 | T055 | T062 |
| RF-09 | T056 | T064 |
| RF-10 | T051 | T061 |
| RNF-01 | T080, T082 | `quickstart.md` §2 |
| RNF-02 | T000, T001, T040 | T066 |
| RNF-05 | Bloco 1 | T065 |
