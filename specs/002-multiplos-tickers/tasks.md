# Tasks: Consulta de múltiplos tickers com cache por ativo

**Input**: Design documents from `/specs/002-multiplos-tickers/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Status**: todas as 49 tarefas concluídas em 2026-09-06.

**Tests**: obrigatórios. O Artigo IV da constituição exige teste antes da
implementação — aqui não é opcional como no template padrão.

## Format: `[ID] [P?] [Story] Description`

- `[P]` — pode rodar em paralelo com outras `[P]` da mesma fase (arquivos distintos)
- `[US1]`, `[US2]`, `[US3]` — história de usuário que a tarefa atende
- Toda tarefa de implementação é precedida pelo seu teste, que deve falhar antes

## Path Conventions

Serviço único, hexagonal. Código em `src/investimentos/`, testes em `tests/`.

---

## Phase 1: Setup

**Purpose**: a única peça de configuração que a feature acrescenta.

- [x] T001 Acrescentar `max_tickers_per_request` (padrão 3) em `src/investimentos/config/settings.py`
- [x] T002 [P] Documentar `MAX_TICKERS_PER_REQUEST` em `.env.example` e no `docker-compose.yml`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: o núcleo que todas as histórias usam. Nenhuma história começa antes.

**⚠️ CRÍTICO**: bloqueia as fases 3, 4 e 5.

- [x] T003 **test** [P] `TooManyTickersError` carrega quantidade pedida e limite, em `tests/unit/domain/test_exceptions.py`
- [x] T004 Implementar `TooManyTickersError` em `src/investimentos/domain/exceptions.py`
- [x] T005 **test** [P] Tipos de resultado: `QuoteResolution` e `QuoteLookup` preservam ordem e expõem `found`/`cached`, em `tests/unit/application/test_quote_lookup.py`
- [x] T006 Implementar `QuoteOrigin`, `QuoteResolution` e `QuoteLookup` em `src/investimentos/application/usecases/get_quote.py`
- [x] T007 Trocar `fetch` por `fetch_many` na porta `src/investimentos/application/ports/quote_provider.py`
- [x] T008 Trocar `get`/`set` por `get_many`/`set_many` na porta `src/investimentos/application/ports/quote_cache.py`

**Checkpoint**: portas e tipos prontos — as histórias podem começar.

---

## Phase 3: User Story 1 - Consultar vários ativos numa chamada (Priority: P1) 🎯 MVP

**Goal**: `GET /ticker` aceita vários códigos e devolve uma lista com as cotações.

**Independent Test**: pedir três códigos válidos e receber as três cotações, na ordem pedida.

### Tests for User Story 1

- [x] T009 **test** [P] [US1] Mapper devolve mapa indexado por código, ignorando símbolo fora do padrão, em `tests/unit/adapters/test_brapi_mapper.py`
- [x] T010 **test** [P] [US1] Cliente monta uma chamada só com os códigos separados por vírgula, em `tests/unit/adapters/test_brapi_client.py`
- [x] T011 **test** [P] [US1] Caso de uso normaliza, deduplica e preserva a ordem, em `tests/unit/application/test_get_quotes.py`
- [x] T012 **test** [US1] Rota devolve lista com três ativos, na ordem pedida, em `tests/integration/test_ticker_lista.py`
- [x] T013 **test** [P] [US1] Lista de um elemento continua sendo lista, em `tests/integration/test_ticker_lista.py`

### Implementation for User Story 1

- [x] T014 [US1] `extract_items` devolve todos os itens de `results`, indexados por `symbol`, em `adapters/outbound/brapi/mapper.py`
- [x] T015 [US1] `BrapiQuoteProvider.fetch_many` monta uma chamada com os códigos unidos por vírgula, em `adapters/outbound/brapi/client.py` (depende de T014)
- [x] T016 [US1] `GetQuotesUseCase.execute` orquestra a consulta e monta o `QuoteLookup`, em `application/usecases/get_quote.py`
- [x] T017 [P] [US1] `TickerLookupItem` e o schema da lista em `adapters/inbound/http/schemas.py`
- [x] T018 [US1] Rota `GET /ticker` com o parâmetro `ticker` repetido, em `adapters/inbound/http/routers/ticker.py`

**Checkpoint**: a consulta múltipla funciona ponta a ponta, ainda sem o ganho de cota.

---

## Phase 4: User Story 2 - Não gastar cota com o que já está em cache (Priority: P2)

**Goal**: cada ativo é procurado no cache individualmente; só os ausentes vão à fonte.

**Independent Test**: aquecer o cache com um ativo, pedir dois, e verificar que a fonte foi chamada só com o novo.

### Tests for User Story 2

- [x] T019 **test** [P] [US2] Cache: `get_many` usa uma leitura só e devolve apenas os presentes, em `tests/unit/adapters/test_redis_cache.py`
- [x] T020 **test** [P] [US2] Cache: `set_many` grava cada um com TTL próprio, em `tests/unit/adapters/test_redis_cache.py`
- [x] T021 **test** [US2] Caso de uso chama a fonte só com os faltantes, em `tests/unit/application/test_get_quotes.py`
- [x] T022 **test** [US2] Tudo em cache resulta em zero chamadas à fonte (SC-002), em `tests/unit/application/test_get_quotes.py`
- [x] T023 **test** [P] [US2] Cache indisponível não impede a consulta (FR-014), em `tests/unit/application/test_get_quotes.py`
- [x] T024 **test** [US2] Resposta marca a origem por ativo (SC-006), em `tests/integration/test_ticker_lista.py`

### Implementation for User Story 2

- [x] T025 [US2] `get_many` com `MGET` e `set_many` com pipeline em `adapters/outbound/cache/redis_cache.py`
- [x] T026 [P] [US2] `NullQuoteCache` acompanha a nova assinatura em `adapters/outbound/cache/null_cache.py`
- [x] T027 [US2] Caso de uso consulta o cache antes da fonte e grava os obtidos (depende de T025)
- [x] T028 [US2] Log registra quantos vieram do cache e quantos da fonte (Artigo IX)

**Checkpoint**: a economia de cota é real e observável na resposta.

---

## Phase 5: User Story 3 - Rota que nomeia o recurso (Priority: P3)

**Goal**: `/ticker/{codigo}` para um ativo, `/ticker` para vários, `/cotacao` deixa de existir.

**Independent Test**: chamar as duas rotas novas e conferir que a antiga devolve 404.

### Tests for User Story 3

- [x] T029 **test** [P] [US3] `/ticker/PETR4` devolve um objeto, não lista, em `tests/integration/test_ticker_item.py`
- [x] T030 **test** [P] [US3] `/cotacao/PETR4` devolve 404 (FR-017), em `tests/integration/test_ticker_item.py`
- [x] T031 **test** [P] [US3] Índice da raiz anuncia as duas rotas novas, em `tests/integration/test_root_index.py`

### Implementation for User Story 3

- [x] T032 [US3] Rota `GET /ticker/{ticker}` no lugar de `/cotacao/{ticker}`, em `routers/ticker.py`
- [x] T033 [US3] Remover `routers/cotacao.py` e sua inclusão em `app.py`
- [x] T034 [P] [US3] Índice da raiz passa a anunciar `/ticker/{ticker}` e `/ticker`, em `routers/root.py` e `schemas.py`

---

## Phase 6: Falha parcial e limites (transversal)

**Purpose**: FR-010, FR-011 e FR-013 atravessam as três histórias.

- [x] T035 **test** [P] Formato inválido derruba a requisição inteira sem chamada externa (SC-005), em `tests/integration/test_ticker_lista.py`
- [x] T036 **test** [P] Código inexistente volta na lista como `notFound` (FR-011), em `tests/integration/test_ticker_lista.py`
- [x] T037 **test** [P] Acima do limite devolve 400 explicando (FR-010), em `tests/integration/test_ticker_lista.py`
- [x] T038 **test** [P] Nenhum código informado devolve 400, em `tests/integration/test_ticker_lista.py`
- [x] T039 **test** [P] `Retry-After` da fonte é repassado no nosso 503 (FR-013), em `tests/unit/adapters/test_brapi_client.py`
- [x] T040 Validação de limite e de lista vazia no caso de uso
- [x] T041 `TooManyTickersError` → 400 em `adapters/inbound/http/error_handlers.py`
- [x] T042 Repasse do `Retry-After` no 503, em `error_handlers.py` e `client.py`
- [x] T043 **test** O limite configurado nunca excede o teto da fonte, em `tests/unit/test_limites.py` (guarda o Complexity Tracking)

---

## Phase 7: Contrato, arquitetura e entrega

- [x] T044 **test** OpenAPI publicado cumpre `contracts/openapi.yaml` da Spec 002, em `tests/integration/test_openapi.py`
- [x] T045 Apontar o teste de contrato para o arquivo da Spec 002 e subir a versão da app para 2.0.0
- [x] T046 **test** Artigo II e X continuam válidos por AST, em `tests/test_architecture.py`
- [x] T047 [P] Contract test da consulta múltipla real, em `tests/contract/test_brapi_contract.py` (confirma CHK024 e CHK025)
- [x] T048 [P] README: rotas, exemplo de consulta múltipla e a nova variável
- [x] T049 Rodar ruff, mypy estrito e a suíte inteira

---

## Ordem de execução

```
Fase 1 → Fase 2 → Fase 3 (US1) → Fase 4 (US2) → Fase 5 (US3) → Fase 6 → Fase 7
```

As fases 3, 4 e 5 são sequenciais por dependência de arquivo, não de história:
todas mexem no caso de uso e nos routers. A Fase 6 depende de as três existirem.

## Rastreabilidade

| Requisito | Tarefas | Teste que o prova |
|---|---|---|
| FR-001 | T016, T018 | T012 |
| FR-002 | (domínio existente) | T035 |
| FR-003 | T016 | T011 |
| FR-004 | T025, T027 | T019, T021 |
| FR-005 | T027 | T021 |
| FR-006 | T015 | T010 |
| FR-007 | T027 | T022 |
| FR-008 | T025 | T020 |
| FR-009 | T017, T027 | T024 |
| FR-010 | T001, T040, T041 | T037, T043 |
| FR-011 | T040, T041 | T035, T036 |
| FR-012 | T018, T032 | T012, T029 |
| FR-013 | T042 | T039 |
| FR-014 | T026 | T023 |
| FR-015 | T017 | T044 |
| FR-016 | T016 | T011 |
| FR-017 | T033 | T030 |
| Artigo X e XI | T017, T034, T045 | T044, T046 |
