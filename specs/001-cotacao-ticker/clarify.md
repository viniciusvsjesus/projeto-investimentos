# Clarificação — Spec 001

Registro das ambiguidades levantadas durante a especificação e como cada uma
foi resolvida. Conforme o Artigo I, nenhum item aqui pode ficar em aberto para
a fase de plano começar.

- **Fonte:** entrevista com Vini, 2026-09-03
- **Método:** perguntas fechadas com alternativas e trade-offs explícitos

---

## Q1 — Qual o escopo funcional do MVP?

**Ambiguidade:** "bater a API e retornar um JSON com uma rota" admite desde um
ativo até um catálogo inteiro.

**Alternativas apresentadas:** um ticker · N tickers · cotação + histórico ·
cotação + dividendos + fundamentos.

**Decisão:** **cotação de um ticker**, uma rota só.

**Justificativa:** é o menor recorte que ainda exercita a arquitetura hexagonal
ponta a ponta — borda HTTP, caso de uso, porta de saída, adapter externo,
cache e tratamento de erro. Escopo maior aumentaria o custo de cada iteração
sem ensinar nada de novo sobre a arquitetura.

**Impacto:** RF-01. Consulta múltipla e histórico foram para "fora de escopo".

---

## Q2 — Qual framework web para a camada de entrada?

**Alternativas apresentadas:** FastAPI + Pydantic · Flask + Marshmallow · Litestar.

**Decisão:** **FastAPI + Pydantic**.

**Justificativa:** gera OpenAPI e Swagger UI automaticamente (equivalente ao
`springdoc` no Spring Boot, ambiente de origem do autor), valida entrada de
forma declarativa e traz injeção de dependência nativa — o que permite manter
o *composition root* explícito sem framework de DI extra. Async nativo casa
com o cliente HTTP e com o Redis assíncrono.

**Impacto:** RF-08, RF-09. FastAPI fica confinado a `adapters/inbound/http/`
por força do Artigo II.

---

## Q3 — O MVP precisa guardar estado?

**Alternativas apresentadas:** nada (stateless) · cache em memória ·
Redis no compose · PostgreSQL no compose.

**Decisão:** **Redis no docker-compose**.

**Justificativa:** cache real, compartilhado entre réplicas, com TTL nativo.
Protege a cota gratuita da BRAPI e torna o compose representativo de um
ambiente de verdade — dois serviços com `healthcheck` e dependência ordenada.

**Consequência aceita:** o Redis é uma dependência a mais para subir. Mitigada
pelo RF-06: se o Redis cair, a API continua servindo cotações direto da fonte.
Isso obriga a porta de cache a ter uma segunda implementação (`NullCache`), o
que satisfaz o Artigo VII — a abstração tem duas implementações reais e um
teste que exige as duas.

**Impacto:** RF-05, RF-06, RN-05, RN-06, CA-02.2.

---

## Q4 — Como tratar o framework SAND, usado pelo autor no trabalho?

**Alternativas apresentadas:** basear no GitHub Spec Kit e adaptar depois ·
receber a documentação do SAND agora · pesquisar na web.

**Decisão:** **seguir o GitHub Spec Kit**, sem adaptação pendente.

**Resolução (2026-09-03):** o autor confirmou que o SAND é o mesmo que o GitHub
Spec Kit. Não há framework separado, não há tradução de artefatos a fazer e não
existe pendência. O fluxo adotado — constitution → specify → clarify → plan →
tasks → implement — é o do Spec Kit e é o definitivo deste projeto.

---

## Q5 — Gerenciador de dependências e build da imagem?

**Alternativas apresentadas:** uv + pyproject · Poetry · pip + requirements.txt.

**Decisão:** **pip + requirements.txt**.

**Justificativa:** é o mecanismo nativo do Python, sem ferramenta adicional para
instalar ou aprender. Reduz a superfície de coisas que podem falhar na máquina
de outra pessoa — coerente com o objetivo declarado de usar Docker para reduzir
complexidade.

**Consequência aceita:** sem lockfile com hash. Mitigada fixando versões exatas
(`==`) em `requirements.txt` e separando `requirements-dev.txt`.

---

## Q6 — Qual estratégia de testes?

**Alternativas apresentadas:** unidade + integração mockada · o mesmo + contract
test real opt-in · só unidade.

**Decisão:** **unidade + integração mockada + contract test real opt-in**.

**Justificativa:** os dois primeiros níveis rodam offline, rápidos e
determinísticos, e cobrem o CI. O contract test é a única prova de que o nosso
mapper corresponde ao que a BRAPI devolve de verdade — especialmente relevante
porque a documentação pública da BRAPI apresenta dois formatos de resposta
(ver `research.md`, ADR-004).

**Impacto:** Artigo IV. Marcador `contract` registrado em `pyproject.toml`,
desabilitado por padrão e ausente do CI.

---

## Q7 — A API terá controle de acesso?

**Alternativas apresentadas:** nenhum · API key via header.

**Decisão:** **nenhum controle no MVP**.

**Justificativa:** o serviço roda em localhost ou rede interna. Autenticação
sem requisito de negócio seria abstração especulativa (Artigo VII).

**Condição de reabertura:** no momento em que o serviço for exposto fora da
rede local, esta decisão precisa ser revista antes do deploy. Registrado como
risco em `plan.md`.

---

## Q8 — O que deve aparecer ao abrir o localhost no navegador?

**Alternativas apresentadas:** redirect `/` → `/docs` · JSON de índice na raiz ·
landing HTML.

**Decisão inicial:** redirect da raiz para o Swagger UI.

**Decisão revista (2026-09-03): JSON de índice na raiz.** Ao ver o Swagger, o
autor foi direto ao ponto: *"não entendi este botão try out, vai ter um botão?
não precisa, só quero o JSON mesmo"*.

**Justificativa da revisão:** o Swagger é uma interface para *explorar* uma API
que você ainda não conhece. Quem já sabe o que quer não precisa de tela nem de
botão — precisa de uma URL que devolva JSON. Manter o Swagger como porta de
entrada colocava um passo entre o usuário e o dado.

**O que mudou na prática:**

- `GET /` devolve JSON com o nome do serviço, o estado e a URL de exemplo
  pronta para colar no navegador — em vez de redirecionar.
- O Swagger continua em `/docs`, porque o FastAPI o gera de graça a partir do
  OpenAPI. Ele deixou de ser o caminho principal, não foi removido.

**Impacto:** RF-08, CA-03.1, CA-03.2 reescritos.

---

## Q9 — Qual geração do endpoint da BRAPI está ativa?

**Contexto:** a ADR-004 registrou que a documentação pública mostrava duas
gerações e que não foi possível confirmar qual estava no ar — o `robots.txt` da
BRAPI bloqueia o acesso automatizado usado na pesquisa.

**Resolução (2026-09-03):** o autor colou o payload real do painel da BRAPI,
com a chamada dele funcionando. A geração ativa é a **v2**:

    GET https://brapi.dev/api/v2/stocks/quote?symbols=B3SA3
    Authorization: Bearer <token>

O formato confirmado traz `symbol` no nível externo do item e os dados de
mercado aninhados sob `data` — detalhe que o mapper agora trata mesclando os
dois níveis, em vez de descartar o externo.

**Impacto:** `BRAPI_QUOTE_PATH` passa a ter o v2 como padrão. O caminho continua
configurável, para permitir voltar ao legado sem recompilar. ADR-004 fechada.
