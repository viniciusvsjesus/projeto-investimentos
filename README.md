# Projeto Investimentos API

API HTTP que expõe cotações de ativos da B3 em um contrato próprio e estável,
isolando os consumidores da fonte externa de dados ([BRAPI](https://brapi.dev)).

Construída inteiramente por **SDD** — desenvolvimento guiado por especificação.
Nenhuma linha de código aqui existe sem um requisito que a originou e um teste
que a prova.

```
┌──────────────┐    HTTP     ┌──────────────────────┐    HTTP    ┌───────┐
│  Consumidor  │ ──────────▶ │  Projeto             │ ─────────▶ │ BRAPI │
│              │ ◀────────── │  Investimentos API   │ ◀───────── │       │
└──────────────┘  contrato   └──────────┬───────────┘   token    └───────┘
                   estável              │ cache
                                   ┌────▼────┐
                                   │  Redis  │
                                   └─────────┘
```

---

## Subir em um comando

Pré-requisito: **Docker**. Nada mais — não é preciso ter Python instalado.

```bash
git clone <url-do-repositorio>
cd projeto-investimentos

cp .env.example .env      # e coloque seu token da BRAPI no arquivo

docker compose up -d
```

Abra <http://localhost:8000/cotacao/PETR4> no navegador. O JSON aparece direto —
sem tela, sem botão.

A raiz <http://localhost:8000> devolve um índice, também em JSON, com o estado do
serviço e a URL de exemplo:

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

Sem token o serviço sobe do mesmo jeito, mas só os tickers de sandbox
(`PETR4`, `VALE3`, `MGLU3`, `ITUB4`) respondem.

## Usar

```bash
curl http://localhost:8000/cotacao/PETR4
```

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

### Rotas

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/cotacao/{ticker}` | **Cotação atual de um ativo** |
| `GET` | `/` | Índice do serviço, em JSON |
| `GET` | `/health` | Saúde do serviço e do cache |
| `GET` | `/openapi.json` | Especificação OpenAPI |
| `GET` | `/docs` | Documentação interativa (opcional — a API é usável sem ela) |

Códigos aceitos seguem o padrão da B3: quatro caracteres começando por letra,
mais um ou dois dígitos, com `F` opcional. Aceita minúsculas.
Exemplos: `PETR4`, `B3SA3`, `BOVA11`, `MXRF11`, `AAPL34`, `petr4f`.

### Erros

Toda falha usa o mesmo corpo, no estilo RFC 9457:

```json
{
  "type": "https://projeto-investimentos/errors/invalid-ticker",
  "title": "Código de ativo inválido",
  "status": 400,
  "detail": "O código 'PETR' não segue o padrão da B3: ...",
  "instance": "/cotacao/PETR"
}
```

| Status | Quando |
|---|---|
| `400` | Código de ativo fora do padrão da B3 — quatro caracteres começando por letra, mais um ou dois dígitos (rejeitado antes de chamar a BRAPI) |
| `404` | Ativo não encontrado |
| `502` | Falha de comunicação, credencial rejeitada ou resposta inesperada da fonte |
| `503` | Cota da BRAPI esgotada |
| `504` | A BRAPI excedeu o tempo limite |

---

## Documentação da API

Existem duas, e elas se vigiam.

**A gerada automaticamente.** O FastAPI monta a especificação OpenAPI 3.1 a
partir do próprio código — tipos dos parâmetros, modelos Pydantic, docstrings e
os status declarados em cada rota. Nada é escrito à mão e nada sai do lugar
quando o código muda:

| URL | O que é |
|---|---|
| `/openapi.json` | A especificação em si. Serve para gerar cliente com `openapi-generator`, importar no Postman ou no Insomnia |
| `/docs` | Swagger UI, para explorar e executar |
| `/redoc` | Redoc, para leitura corrida |

**A escrita antes do código.** `specs/001-cotacao-ticker/contracts/openapi.yaml`
foi redigida na fase de plano, antes de existir implementação. Ela é o contrato
acordado, não um retrato do que o código faz.

O que liga as duas é `tests/integration/test_openapi.py`: ele busca a
especificação gerada e confere se ela cumpre a escrita — rotas, `operationId`,
status de resposta, campos e **tipos**. Se alguém alterar uma resposta e
esquecer do contrato, o build quebra.

Foi exatamente assim que se descobriu que `price` estava sendo publicado como
anulável: o campo é obrigatório e nunca vem nulo, mas o serializador tinha
retorno `float | None`, e qualquer gerador de cliente produziria um
`Optional<Double>` para ele.

## Conferir que está vindo dado real

Depois do `docker compose up -d`, abra no Chrome:

```
http://localhost:8000/cotacao/PETR4
```

O JSON tem que trazer `"source": "brapi"` e um `quotedAt` recente. Se vier
`"cached": true` na primeira vez, é porque o Redis ainda tinha a cotação da
execução anterior — normal.

Para provar que o nosso mapper corresponde ao que a BRAPI devolve **hoje**,
rode o teste de contrato, que bate na API de verdade com o seu token:

```bash
docker compose exec api pytest -m contract -v
```

Ele verifica o endpoint, o formato do payload e a conversão para o nosso
contrato. É a checagem que pega uma mudança de contrato da fonte antes do
usuário pegar.

## Segurança e segredos

**O token da BRAPI nunca entra no repositório.** Isso não é recomendação, é o
Artigo V da constituição do projeto, e há teste automatizado que falha se for
violado.

- O token vive apenas no `.env`, que está no `.gitignore` desde o primeiro commit.
- `.env.example` é versionado, com placeholder e nenhum valor real.
- O token viaja no header `Authorization: Bearer`, **nunca** em query string — a
  própria documentação da BRAPI alerta que query string vaza para histórico de
  navegador e log de servidor.
- Nas configurações ele é um `SecretStr`: não aparece em `repr()`, em log nem em
  serialização acidental.
- Nenhuma resposta de erro devolve stack trace ou detalhe interno.

Antes de publicar no GitHub, confirme:

```bash
git status --short           # .env não pode aparecer
git check-ignore -v .env     # deve confirmar que está ignorado
```

> Se um token vazar para o histórico do Git, **rotacione o token na BRAPI**.
> Remover o commit não basta: o valor já saiu.

---

## Configuração

Todas as variáveis vêm do ambiente, com padrão sensato. Ver `.env.example`.

| Variável | Padrão | O que faz |
|---|---|---|
| `BRAPI_TOKEN` | — | Token da BRAPI. Vazio limita ao sandbox. |
| `BRAPI_BASE_URL` | `https://brapi.dev` | Host da fonte |
| `BRAPI_QUOTE_PATH` | `/api/v2/stocks/quote?symbols={ticker}` | Endpoint de cotação. v2 é o ativo; o legado `/api/quote/{ticker}` continua suportado (ADR-004) |
| `BRAPI_TIMEOUT_SECONDS` | `8.0` | Tempo limite da chamada externa |
| `REDIS_URL` | `redis://redis:6379/0` | Cache. Vazio desliga o cache. |
| `CACHE_TTL_SECONDS` | `60` | Validade da cotação em cache |
| `APP_ENV` | `development` | `development` usa log legível; qualquer outro valor usa JSON |
| `LOG_LEVEL` | `INFO` | Nível de log |
| `API_PORT` | `8000` | Porta exposta no host |

---

## Arquitetura

Hexagonal (Ports & Adapters), com a dependência apontando **sempre para dentro**:

```
adapters  ──▶  application  ──▶  domain
 (borda)       (casos de uso)     (núcleo)
```

| Camada | O que pode importar | O que contém |
|---|---|---|
| `domain/` | só a biblioteca padrão do Python | `Ticker`, `Quote`, exceções de negócio |
| `application/` | só `domain/` | portas (`Protocol`) e o caso de uso `GetQuote` |
| `adapters/` | tudo | FastAPI, httpx, Redis, tradução de contrato |
| `config/` | tudo | settings, log e o *composition root* |

O que isso compra na prática: trocar FastAPI por outro framework, ou Redis por
outro cache, não toca uma linha de `domain/` nem de `application/`. E a regra
não é um combinado verbal — `tests/test_architecture.py` percorre a AST de cada
módulo e **quebra o build** se alguém importar FastAPI dentro do domínio.

O único lugar que instancia adapters concretos é `config/container.py`.

---

## Desenvolvimento

Tudo roda em container; não é preciso instalar Python na máquina.

```bash
# sobe com hot reload e a suíte de testes disponível dentro do container
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# testes
docker compose exec api pytest -v

# lint e tipos
docker compose exec api ruff check .
docker compose exec api mypy
```

### Testes

| Nível | O que cobre | Rede | No CI |
|---|---|---|---|
| Unidade | domínio e casos de uso | não | sim |
| Integração | rota ponta a ponta, BRAPI mockada por `respx` | não | sim |
| Arquitetura | o Artigo II, via AST | não | sim |
| Contrato | a BRAPI real | **sim** | não |

O contract test é opt-in porque consome cota do token:

```bash
docker compose exec api pytest -m contract -v
```

Ele é a única prova de que o nosso mapper corresponde ao que a BRAPI devolve
hoje. Se ele falhar, quem está desatualizado é a nossa documentação de
contrato — não a BRAPI.

Independente dele, o payload real do painel da BRAPI está congelado como fixture
(`brapi_v2_payload_real`) e é exercitado por testes que rodam **offline e sem
token** — regressão permanente contra mudança silenciosa na leitura do contrato.

### Rodar sem Docker

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn investimentos.main:app --reload --app-dir src
```

---

## O processo: SDD com o GitHub Spec Kit

Este projeto não começou pelo código. Começou pela constituição, passou por
entrevista, especificação e plano, e só então virou implementação.

O fluxo é o do [GitHub Spec Kit](https://github.com/github/spec-kit), e a
ferramenta oficial está instalada no repositório — não é uma imitação do
processo, é o Spec Kit de verdade (versão 1.0.4, integração Claude, scripts em
shell).

### Os comandos

Dentro do Claude Code, na ordem:

| Comando | O que faz |
|---|---|
| `/speckit-constitution` | Cria ou atualiza os princípios que governam o projeto |
| `/speckit-specify` | Descreve o que construir — requisitos e histórias de usuário |
| `/speckit-clarify` | Levanta e resolve as ambiguidades (antes do plano) |
| `/speckit-plan` | Traduz a especificação em arquitetura e decisões técnicas |
| `/speckit-checklist` | Gera o checklist de qualidade dos requisitos |
| `/speckit-tasks` | Deriva o backlog executável do plano |
| `/speckit-analyze` | Confere consistência entre spec, plano e tarefas |
| `/speckit-implement` | Executa as tarefas |
| `/speckit-converge` | Compara o código com spec/plano e anexa o que ficou faltando |

`clarify`, `checklist` e `analyze` são opcionais no Spec Kit. Neste projeto os
três são usados: a constituição exige que ambiguidade vire pergunta registrada
(Artigo I) e que todo requisito tenha teste (Artigo IV).

### O que fica no repositório

| Caminho | O que é |
|---|---|
| `.specify/memory/constitution.md` | Os 10 artigos que o código não pode violar |
| `.specify/templates/` | Moldes oficiais de spec, plano, tarefas, checklist e constituição |
| `.specify/scripts/bash/` | Scripts que os comandos chamam para resolver caminhos e pré-requisitos |
| `.specify/workflows/` | Definição do ciclo completo |
| `.claude/skills/speckit-*/` | Os comandos em si, como skills do Claude Code |
| `specs/NNN-slug/` | Os artefatos de cada feature |

`.specify/feature.json` aponta para a feature ativa e **não** é versionado — é
estado da sua máquina, e o próprio Spec Kit o ignora.

### Os artefatos da Spec 001

| Arquivo | O que responde |
|---|---|
| `spec.md` | O quê e por quê |
| `clarify.md` | Cada ambiguidade e como foi resolvida (Q1 a Q9) |
| `plan.md` | Como, com o portão de conformidade constitucional |
| `research.md` | Decisões técnicas e alternativas descartadas (ADR-001 a ADR-008) |
| `data-model.md` | Estruturas do domínio e contratos |
| `contracts/` | O OpenAPI que publicamos e o contrato que consumimos |
| `tasks.md` | Backlog rastreável até o requisito |
| `checklists/requirements.md` | Revisão de qualidade dos requisitos |
| `quickstart.md` | Roteiro de validação manual |

Todo requisito tem rastro até o teste que o prova — a tabela está em
`plan.md` §8.

### Para a próxima feature

É só rodar `/speckit-specify` descrevendo o que você quer. O Spec Kit cria
`specs/002-<slug>/`, aponta o `feature.json` para lá e conduz o resto do ciclo.
A constituição vale para ela também.

Para mexer na própria instalação do Spec Kit (atualizar, trocar de integração,
ver o que está disponível):

```bash
uv tool install specify-cli
specify check
```

### Duas coisas que o processo pegou

Vale reparar em defeitos que código-primeiro deixaria passar: a regra do ticker
reprovava `B3SA3` — um código legítimo da própria B3 — e foi um teste que expôs
isso; e o `symbol` do endpoint v2 fica fora de `data`, detalhe que só apareceu
quando o payload real entrou como fixture.

## Escopo do MVP

Nesta entrega: **uma rota**, cotação de **um** ativo.

Deliberadamente fora, e registrado em `spec.md` §3: consulta de vários ativos,
histórico, dividendos, fundamentalistas, FIIs, cripto, autenticação da nossa
API, banco de dados e cálculo de carteira. Cada um é candidato a uma spec
própria — nenhum é "já que estamos aqui".

## Licença

MIT. Ver [LICENSE](LICENSE).
