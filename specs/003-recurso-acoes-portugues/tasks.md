# Tasks: Recurso `acoes`, contrato em português e validade

**Input**: Design documents from `/specs/003-recurso-acoes-portugues/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: obrigatórios (Artigo IV).

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Foundational — a validade sobe do cache até a borda

**⚠️ Bloqueia a US3.** As demais histórias não dependem desta fase.

- [ ] T001 **test** [P] `CachedQuote` carrega cotação e validade, em `tests/unit/application/test_quote_lookup.py`
- [ ] T002 Criar `CachedQuote` em `application/ports/quote_cache.py` e mudar `get_many` para devolvê-lo
- [ ] T003 **test** `get_many` traz o TTL restante numa ida só; `-1` e `-2` viram ausência de validade, em `tests/unit/adapters/test_redis_cache.py`
- [ ] T004 `RedisQuoteCache.get_many` com pipeline `GET`+`TTL` e normalização do TTL
- [ ] T005 [P] `NullQuoteCache` acompanha a assinatura
- [ ] T006 **test** `QuoteResolution.valid_for` e `QuoteLookup.min_valid_for`, em `tests/unit/application/test_quote_lookup.py`
- [ ] T007 `QuoteResolution` ganha `valid_for`; o caso de uso recebe o TTL cheio por injeção
- [ ] T008 `Container` injeta `cache_ttl_seconds`, ou zero quando o cache está desligado

---

## Phase 2: User Story 1 - URL que descreve o que devolve (P1) 🎯

**Independent Test**: `/acoes/ITSA4` devolve objeto; `/acoes?ticker=…` devolve lista.

- [ ] T009 **test** [P] [US1] `/acoes/ITSA4` devolve um objeto, em `tests/integration/test_acoes_item.py`
- [ ] T010 **test** [P] [US1] `/acoes?ticker=…` devolve lista, e lista de um continua lista, em `tests/integration/test_acoes_lista.py`
- [ ] T011 **test** [P] [US1] `/ticker/ITSA4` e `/ticker?…` devolvem 404, em `tests/integration/test_acoes_item.py`
- [ ] T012 [US1] Criar `routers/acoes.py` e remover `routers/ticker.py`
- [ ] T013 [US1] Trocar o router incluído em `app.py` e atualizar a descrição

---

## Phase 3: User Story 2 - Contrato em português (P2)

**Independent Test**: nenhum nome de campo em inglês em nenhuma resposta.

- [ ] T014 **test** [P] [US2] Varredura: nenhuma resposta contém os nomes antigos, em `tests/integration/test_contrato_portugues.py`
- [ ] T015 **test** [P] [US2] `situacao` usa `encontrada`/`naoEncontrada`, em `tests/integration/test_contrato_portugues.py`
- [ ] T016 **test** [P] [US2] O corpo de erro **mantém** os nomes do RFC 9457, em `tests/integration/test_error_contract.py`
- [ ] T017 [US2] Traduzir `CotacaoResponse` e `AcaoConsultada` por alias em `schemas.py`
- [ ] T018 [P] [US2] Traduzir índice e saúde (`situacao`, `dependencias`, valores)
- [ ] T019 [P] [US2] Atualizar `routers/root.py` e `routers/health.py` para os schemas novos

---

## Phase 4: User Story 3 - A resposta diz por quanto tempo vale (P3)

**Independent Test**: consultar duas vezes e ver o `max-age` decrescer.

- [ ] T020 **test** [P] [US3] Cálculo do cabeçalho: menor validade, `no-store` sem cotação, em `tests/unit/adapters/test_cache_headers.py`
- [ ] T021 [US3] Criar `adapters/inbound/http/cache_headers.py`
- [ ] T022 **test** [US3] Item e lista trazem `Cache-Control` com a validade, em `tests/integration/test_cache_control.py`
- [ ] T023 **test** [P] [US3] Erro nunca é cacheável, em `tests/integration/test_cache_control.py`
- [ ] T024 [US3] Aplicar o cabeçalho nas duas rotas
- [ ] T025 [US3] `no-store` nas respostas de erro, em `error_handlers.py`

---

## Phase 5: Contrato, versão e entrega

- [ ] T026 Subir a versão da aplicação para 3.0.0 em `settings.py`
- [ ] T027 **test** OpenAPI publicado cumpre `contracts/openapi.yaml` da Spec 003, e nenhum caminho tem prefixo de versão
- [ ] T028 **test** Artigos II e X continuam válidos por AST, em `tests/test_architecture.py`
- [ ] T029 [P] README com as rotas, os campos em português e o `Cache-Control`
- [ ] T030 Rodar ruff, mypy estrito e a suíte inteira (SC-007: os 182 testes anteriores continuam verdes)

---

## Ordem

```
Fase 1 → Fase 2 → Fase 3 → Fase 4 → Fase 5
```

A Fase 1 bloqueia a 4. As fases 2 e 3 mexem nos mesmos arquivos e por isso são
sequenciais, não por dependência de história.

## Rastreabilidade

| Requisito | Tarefas | Teste |
|---|---|---|
| FR-001 | T012 | T009 |
| FR-002 | T012 | T010 |
| FR-003 | T012, T013 | T011 |
| FR-004 | T017, T018 | T014 |
| FR-005 | T017 | T015 |
| FR-006 | — (preservado) | T016 |
| FR-007 | T017 | T027 |
| FR-008 | T021, T024 | T022 |
| FR-009 | T004, T007 | T003 |
| FR-010 | T021 | T020 |
| FR-011 | T025 | T023 |
| FR-012 | T021 | T020 |
| FR-013 | T019 | T018 |
| FR-014 | — | T027 |
| SC-007 | — | T030 |
