# Implementation Plan: Recurso `acoes`, contrato em português e validade na resposta

**Branch**: `003-recurso-acoes-portugues` | **Date**: 2026-09-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-recurso-acoes-portugues/spec.md`

## Summary

Três mudanças de **fronteira**, nenhuma de domínio: o recurso passa a se chamar
`acoes` e a ser nomeado pelo dado que devolve; todo o contrato passa a falar
português; e a resposta passa a informar por quanto tempo a cotação ainda vale.

A abordagem técnica cabe em uma frase: **nada abaixo de `adapters/inbound/http/`
muda de nome**. O domínio segue em inglês porque é a linguagem ubíqua do código
(Artigo X); a tradução acontece exatamente onde a Spec 001 já traduzia o
vocabulário da BRAPI — na borda.

A única mudança que atravessa camadas é a validade: para anunciar o tempo
**restante**, o cache precisa dizer quanto falta, e isso sobe do adapter até a
borda por uma extensão pequena e explícita do contrato da porta.

## Technical Context

**Language/Version**: Python 3.12 (a suíte também roda em 3.10)

**Primary Dependencies**: FastAPI 0.115, Pydantic 2.10, httpx 0.27, redis 5.2 — nenhuma nova

**Storage**: Redis como cache com TTL. `GET` e `TTL` no mesmo pipeline resolvem a validade sem ida extra

**Testing**: pytest 8.3 com pytest-asyncio e respx; contract test opt-in

**Target Platform**: contêiner Linux, `docker compose up -d`

**Project Type**: serviço web (API HTTP), arquitetura hexagonal

**Performance Goals**: continua uma ida ao Redis por operação e no máximo uma chamada externa por requisição

**Constraints**: `max-age` nunca maior que a validade real (SC-004); nenhum comportamento das Specs 001 e 002 regride (SC-007)

**Scale/Scope**: uso pessoal; o recurso escasso continua sendo a cota da fonte

## Constitution Check

*GATE: passar antes da Fase 0. Reavaliado após a Fase 1.* Constituição v1.1.0.

| Artigo | Verificação | Situação |
|---|---|---|
| I — Spec antes do código | Clarificada, sem marcador em aberto | ✅ |
| II — Hexagonal | Só a borda muda de vocabulário; domínio intocado | ✅ |
| III — SOLID | A porta de cache ganha informação, não um método novo | ✅ |
| IV — Teste antes | Todo FR com teste planejado (§7) | ✅ |
| V — Segredos | Nada muda | ✅ |
| VI — Docker | Nenhuma variável nova | ✅ |
| VII — Simplicidade | `ETag` e `/v1/` deliberadamente fora — ver §6 | ✅ |
| VIII — Erro é contrato | Ver a divergência do RFC 9457 em §4 | ⚠️ resolvido |
| IX — Observabilidade | Sem mudança | ✅ |
| X — DDD | Domínio segue em inglês; tradução na fronteira | ✅ |
| XI — Design de API | Recurso nomeado pelo dado, coleção plural com o item dentro | ✅ |

Portão **verde**.

## Project Structure

### Documentation (this feature)

```text
specs/003-recurso-acoes-portugues/
├── spec.md  plan.md  research.md  data-model.md  quickstart.md
├── contracts/openapi.yaml
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

**Nenhum arquivo novo fora da borda.** O diff desta feature é quase todo em dois
arquivos.

```text
src/investimentos/
├── domain/                        INTOCADO — Quote e Ticker seguem em inglês
├── application/
│   ├── ports/quote_cache.py       + CachedQuote (cotação + validade restante)
│   └── usecases/get_quote.py      QuoteResolution ganha valid_for
├── adapters/
│   ├── inbound/http/
│   │   ├── routers/acoes.py       NOVO — substitui ticker.py
│   │   ├── routers/root.py        índice em português
│   │   ├── schemas.py             TODO o vocabulário de saída em português
│   │   └── cache_headers.py       NOVO — calcula o Cache-Control
│   └── outbound/cache/
│       ├── redis_cache.py         pipeline GET+TTL
│       └── null_cache.py          acompanha a assinatura
└── config/container.py            injeta o TTL no caso de uso
```

## Design

### 1. As duas rotas

| Antes | Agora | Devolve |
|---|---|---|
| `GET /ticker/{ticker}` | `GET /acoes/{ticker}` | um objeto |
| `GET /ticker?ticker=…` | `GET /acoes?ticker=…` | uma lista |

A redundância some porque o recurso deixou de se chamar como o filtro. `acoes` é
o **dado**; `ticker` é o **identificador** — que é o papel dele.

Uma raiz só, no plural, com o item dentro: `/acoes` é a coleção e `/acoes/ITSA4`
é um item dela. Duas raízes (`/acao` e `/acoes`) seriam dois nomes para a mesma
coisa, e o consumidor não teria como deduzir uma da outra.

### 2. A tradução do contrato

Acontece **inteiramente** em `schemas.py`, por alias do Pydantic. Nenhuma outra
camada aprende português.

| Campo hoje | Campo novo |
|---|---|
| `shortName` | `nomeCurto` |
| `longName` | `nomeLongo` |
| `currency` | `moeda` |
| `price` | `preco` |
| `change` | `variacao` |
| `changePercent` | `variacaoPercentual` |
| `marketCap` | `valorDeMercado` |
| `quotedAt` | `cotadoEm` |
| `source` | `fonte` |
| `cached` | `emCache` |
| `status` (item da lista) | `situacao` — `encontrada` \| `naoEncontrada` |
| `quote` (item da lista) | `cotacao` |

`ticker` e `volume` ficam como estão: a primeira é a palavra corrente do mercado
brasileiro e o nome do nosso Value Object; a segunda é a mesma nas duas línguas.

### 3. A validade restante

O ponto que exige atravessar camadas. Anunciar o TTL configurado seria mentir:
uma cotação que entrou no cache há 45 segundos com TTL de 60 vale 15, não 60.

```
Redis                     porta                    caso de uso              borda
  │                         │                          │                      │
  │ pipeline GET+TTL        │                          │                      │
  ├────────────────────────▶│ CachedQuote(quote, ttl)  │                      │
  │  (uma ida só)           ├─────────────────────────▶│ QuoteResolution      │
  │                         │                          │   .valid_for         │
  │                         │                          ├─────────────────────▶│
  │                         │                          │      max-age = menor │
```

| Origem da cotação | `valid_for` |
|---|---|
| Cache | o que o Redis informou de TTL restante |
| Fonte | o TTL cheio — acabou de ser gravada |
| Não encontrada | nenhum |
| Cache desligado | zero → `no-store` |

Na lista, vence o **menor**: a resposta inteira deixa de servir quando o
primeiro item vence. Sem nenhuma cotação válida, `no-store`.

### 4. Divergência descoberta no plano: RFC 9457

O FR-006, lido ao pé da letra, mandaria traduzir também os campos do corpo de
erro — `type`, `title`, `status`, `detail`, `instance`.

**Não serão traduzidos.** Esses nomes não são escolha nossa: são o RFC 9457, e
são o que dá sentido ao `Content-Type: application/problem+json` que a API já
declara. Traduzi-los produziria um corpo que **diz** ser problem+json sem ser —
um consumidor genérico de erro deixaria de entender a resposta.

O que já está em português são os **valores** — `title` e `detail` —, que é
justamente a parte destinada a humanos. O erro já fala português onde importa.

O FR-006 foi ajustado na spec para dizer isso explicitamente. É o Artigo VIII
prevalecendo sobre uma leitura literal: erro é contrato, e contrato padronizado
vale mais que consistência cosmética.

### 5. Mapeamento de erros

Sem mudança de status. Só os caminhos no campo `instance` acompanham as rotas
novas.

### 6. Complexity Tracking

| Violação | Por que é necessária | Alternativa mais simples rejeitada porque |
|---|---|---|
| Nenhuma | — | — |

**Deliberadamente NÃO construído**, por força do Artigo VII e por decisão
explícita do autor na clarificação:

- **`ETag` e `304`.** Metade do ganho vem só do `Cache-Control`, e é a metade
  barata. `ETag` exigiria hash estável da representação e tratamento de
  `If-None-Match` em duas rotas.
- **Prefixo `/v1/`.** Não há consumidor externo. Versionar por mudança, como o
  Artigo XI permite.
- **Rota antiga como apelido.** O FR-003 manda remover.
- **`Vary` e negociação de conteúdo.** A API serve um formato só.

## 7. Rastreabilidade requisito → projeto → teste

| Req. | Onde | Teste que falha se violado |
|---|---|---|
| FR-001 | `routers/acoes.py` | `integration/test_acoes_item.py::test_devolve_um_objeto` |
| FR-002 | `routers/acoes.py` | `integration/test_acoes_lista.py::test_devolve_lista` |
| FR-003 | `app.py` | `integration/test_acoes_item.py::test_rota_ticker_sumiu` |
| FR-004 | `schemas.py` | `integration/test_contrato_portugues.py::test_sem_campo_em_ingles` |
| FR-005 | `schemas.py` | `integration/test_contrato_portugues.py::test_situacao_em_portugues` |
| FR-006 | `error_handlers.py` | `integration/test_error_contract.py::test_erro_segue_rfc_9457` |
| FR-007 | `schemas.py` | `integration/test_openapi.py` |
| FR-008 | `cache_headers.py` | `integration/test_cache_control.py::test_resposta_traz_validade` |
| FR-009 | `redis_cache.py`, `get_quote.py` | `unit/adapters/test_redis_cache.py::test_get_many_traz_o_ttl_restante` |
| FR-010 | `cache_headers.py` | `unit/adapters/test_cache_headers.py::test_lista_usa_o_menor` |
| FR-011 | `error_handlers.py` | `integration/test_cache_control.py::test_erro_nao_e_cacheavel` |
| FR-012 | `cache_headers.py` | `unit/adapters/test_cache_headers.py::test_sem_cotacao_e_no_store` |
| FR-013 | `routers/root.py` | `integration/test_root_index.py` |
| FR-014 | — | `integration/test_openapi.py::test_nenhum_caminho_tem_prefixo_de_versao` |
| SC-007 | toda a suíte | os 182 testes das Specs 001 e 002 |

## 8. Riscos

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| O `TTL` do Redis devolver `-1`/`-2` (sem expiração / inexistente) e virar `max-age` negativo | Média | Médio | Normalizado no adapter: valor não positivo vira ausência de validade |
| Tradução deixar passar um campo em inglês | Média | Baixo | Teste varre a resposta inteira procurando os nomes antigos |
| Regressão nas Specs 001 e 002 ao renomear | Média | Alto | Os 182 testes existentes rodam antes de fechar (SC-007) |
| `max-age` maior que a validade real | Baixa | Médio | Vem do TTL do Redis, não do configurado; teste compara os dois |
