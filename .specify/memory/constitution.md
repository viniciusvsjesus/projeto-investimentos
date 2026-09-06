# Constituição do Projeto Investimentos

> Documento de governança. Toda especificação, plano, tarefa e linha de código
> deste repositório é avaliada contra estes artigos. Em caso de conflito entre
> um artigo e uma decisão de implementação, o artigo vence — ou o artigo é
> emendado explicitamente (ver Artigo XII).

- **Versão:** 1.1.0
- **Ratificada em:** 2026-09-03
- **Última emenda:** 2026-09-06

---

## Artigo I — Especificação antes de código

Nenhuma linha de código de produção é escrita sem uma especificação aprovada
em `specs/<feature>/spec.md`.

O fluxo é sequencial e cada etapa é um artefato versionado no Git:

```
constitution → specify → clarify → plan → tasks → implement → analyze
```

1. **specify** — o QUÊ e o PORQUÊ. Sem tecnologia, sem nome de biblioteca.
2. **clarify** — toda ambiguidade vira uma pergunta explícita e uma resposta
   registrada. Nada de suposição silenciosa.
3. **plan** — o COMO. Arquitetura, contratos, modelo de dados, decisões
   técnicas com alternativas descartadas e o motivo.
4. **tasks** — o backlog executável, rastreável até o requisito de origem.
5. **implement** — código, guiado pelas tarefas.

Toda incerteza é marcada no texto com `[NEEDS CLARIFICATION: pergunta]` e
**bloqueia** o avanço para a fase seguinte até ser resolvida em `clarify.md`.

## Artigo II — Arquitetura hexagonal (Ports & Adapters)

O código é organizado em três anéis, com a dependência apontando **sempre para
dentro**:

```
adapters  ──▶  application  ──▶  domain
(borda)        (casos de uso)     (núcleo)
```

Regras invioláveis:

- `domain/` não importa nada de `application/` nem de `adapters/`, e não
  importa **nenhuma** biblioteca de terceiros. Apenas a biblioteca padrão do
  Python. Se o domínio precisa de FastAPI, Pydantic, httpx ou Redis para
  existir, o desenho está errado.
- `application/` não importa nada de `adapters/`. Ele define **portas**
  (interfaces) e depende só delas.
- `adapters/` implementa as portas. É a única camada que conhece HTTP, Redis,
  a BRAPI, variáveis de ambiente e qualquer outro detalhe de infraestrutura.
- Trocar FastAPI por outro framework, ou Redis por Memcached, não pode exigir
  mudança em `domain/` nem em `application/`. Este é o teste prático da
  arquitetura.

A montagem das dependências acontece em um único lugar — o *composition root*
(`config/container.py`). Nenhuma outra parte do código instancia adapters.

## Artigo III — SOLID como critério de revisão

Cada princípio tem um significado operacional aqui, não decorativo:

- **SRP** — uma classe, um motivo para mudar. O cliente da BRAPI faz HTTP; o
  mapper traduz JSON para o domínio; o caso de uso orquestra. Não se juntam.
- **OCP** — adicionar uma nova fonte de cotação é adicionar um adapter novo,
  não editar o caso de uso.
- **LSP** — qualquer implementação de uma porta é substituível pela outra sem
  o chamador perceber. Um `NullCache` tem que se comportar como cache válido.
- **ISP** — portas pequenas e focadas. `QuoteProviderPort` não ganha método de
  dividendos "porque um dia vai precisar".
- **DIP** — módulos de alto nível dependem de abstrações. O caso de uso recebe
  as portas pelo construtor; ele nunca as constrói nem as importa de
  `adapters/`.

## Artigo IV — Teste antes da implementação

Nenhuma tarefa de implementação é considerada concluída sem teste automatizado.
A ordem obrigatória é: **teste escrito → teste falhando → implementação →
teste passando**.

Três níveis, com propósitos distintos:

| Nível | Alvo | I/O real | Roda no CI |
|---|---|---|---|
| Unidade | `domain/` e `application/` | Não | Sempre |
| Integração | rota HTTP ponta a ponta, BRAPI mockada | Não | Sempre |
| Contrato | BRAPI real | Sim | Sob demanda (`-m contract`) |

O teste de contrato existe para detectar quebra de contrato da API externa.
Ele é opt-in porque consome cota do token e depende de rede — mas ele é a
única prova de que nosso mapper corresponde à realidade.

Cobertura não é meta numérica. A regra é: **todo requisito funcional da spec
tem pelo menos um teste que falharia se o requisito fosse violado.**

## Artigo V — Segredos nunca tocam o repositório

- Token da BRAPI, senhas e credenciais vivem exclusivamente em variáveis de
  ambiente, carregadas de um `.env` **não versionado**.
- `.env.example` é versionado, com placeholders óbvios e zero valor real.
- `.gitignore` bloqueia `.env`, `.env.*` (exceto `.env.example`), chaves e
  artefatos de credencial antes do primeiro commit.
- Segredo nunca aparece em log, em mensagem de erro, em resposta HTTP, na URL
  ou no `repr()` de um objeto. O token vai no header `Authorization`, jamais em
  query string.
- Se um segredo vazar para o histórico do Git, o remédio é **rotacionar o
  token**, não apenas remover o commit.

## Artigo VI — Docker é o ambiente canônico

O projeto sobe em qualquer máquina com Docker através de **um único comando**:

```
docker compose up -d
```

Sem instalar Python, sem criar virtualenv, sem passo manual. Consequências
obrigatórias:

- Toda dependência de runtime está declarada e fixada.
- A imagem roda como usuário **não-root**.
- Todo serviço do compose tem `healthcheck`; quem depende de outro usa
  `depends_on: condition: service_healthy`.
- Nenhuma configuração fica *hardcoded* na imagem — tudo entra por variável de
  ambiente com padrão sensato.

## Artigo VII — Simplicidade (anti-especulação)

Constrói-se o que a spec pede. Nada além.

- Nada de camada de abstração "para o futuro" sem requisito que a justifique.
- Nada de padrão de projeto sem problema concreto que ele resolva.
- Nada de configuração para um cenário que não existe.
- Se uma abstração tem exatamente uma implementação e nenhum teste que exija a
  segunda, ela precisa se justificar ou ser removida.

Toda violação deliberada deste artigo é registrada em `plan.md`, na seção
*Complexity Tracking*, com o motivo. Complexidade não documentada é dívida.

## Artigo VIII — Erro é parte do contrato

A API nunca vaza exceção crua nem *stack trace*.

- O domínio lança exceções de domínio (`InvalidTickerError`,
  `QuoteNotFoundError`), que não sabem o que é HTTP.
- O adapter de entrada traduz exceção de domínio em status HTTP.
- Toda resposta de erro tem o mesmo formato, documentado no OpenAPI.
- Falha da dependência externa vira `502`/`503` — nunca `500` silencioso e
  nunca `200` com corpo vazio.

## Artigo IX — Observabilidade mínima

- Log estruturado, com nível configurável por ambiente.
- Toda chamada à API externa registra ticker, latência e resultado — **sem o
  token**.
- Endpoint `/health` reporta o estado do próprio serviço e de suas
  dependências, e é o que o Docker consulta.

## Artigo X — Domain-Driven Design

O domínio é modelado com os conceitos do negócio, não com estruturas genéricas
carregando dados de um lado para o outro.

- **Linguagem ubíqua.** O nome no código é o nome que se usa ao falar do
  assunto. `Ticker`, `Quote`, `Cotação` — não `Data`, `Info`, `Manager`,
  `Helper`. Se a conversa com uma pessoa de negócio usa uma palavra que o código
  não tem, falta um conceito no modelo.
- **Value Object por padrão.** Quando dois objetos com os mesmos valores são a
  mesma coisa, eles são Value Objects: imutáveis, comparados por valor, sem
  identidade. Entidade só quando existe identidade que sobrevive à mudança de
  atributo. `Ticker` e `Quote` são Value Objects — e é por isso que o preço não
  pode ser alterado depois de construído.
- **Invariante vive no modelo.** A regra que define o que é válido fica no
  construtor do objeto, não numa camada de validação à parte. Consequência
  prática: se o objeto existe, ele é válido, e nenhuma outra camada precisa
  revalidar. Um `Ticker` mal formado não chega a existir.
- **Domínio não é anêmico.** Comportamento mora junto do dado. Um modelo que é
  só um saco de atributos, manipulado por "services" de fora, é estrutura de
  dados com nome de domínio.
- **Contexto delimitado.** O contexto deste serviço é *cotação de ativos*.
  Conceito de outro contexto — carteira, posição, imposto — não entra no modelo
  sem uma spec que o justifique, mesmo que "fosse fácil".
- **Tradução na fronteira.** O vocabulário de uma fonte externa não vira o nosso
  vocabulário. `regularMarketPrice` é palavra da BRAPI; do lado de dentro é
  `price`. O tradutor fica no adapter, nunca no domínio.

## Artigo XI — Design de API

A interface HTTP é contrato público. Ela é desenhada, não é consequência
acidental de como o código ficou organizado.

- **O caminho nomeia o recurso; o verbo mora no método.** `GET /ticker/PETR4`,
  nunca `GET /buscarCotacao`. Nada de verbo no caminho.
- **Item e coleção têm formas próprias e previsíveis.** `/ticker/{codigo}`
  devolve **um objeto**. `/ticker` devolve **uma lista**, e continua devolvendo
  uma lista quando o resultado tem um elemento só ou nenhum. O consumidor nunca
  precisa checar o tipo antes de ler.
- **Filtro e seleção vão em parâmetro de consulta.** O caminho identifica *o
  quê*; a query diz *quais* e *como*. Paginação, ordenação e filtro nunca viram
  segmento de caminho.
- **O contrato é nosso.** Nenhum nome de campo, código de erro ou formato de
  data vaza de uma fonte externa para a nossa resposta. Se a fonte mudar, muda o
  tradutor — a resposta que publicamos permanece.
- **Status HTTP tem significado, e ele é respeitado.** `400` é erro de quem
  chamou; `404` é recurso inexistente; `5xx` é falha nossa ou da fonte. Nunca
  `200` com corpo de erro dentro, nunca `500` para entrada inválida.
- **Erro é resposta, não acidente.** Todo erro tem o mesmo corpo, documentado no
  OpenAPI, sem stack trace e sem detalhe interno (ver Artigo VIII).
- **Nomes consistentes na fronteira.** Um estilo só para os campos em toda a
  API. Campo com o mesmo significado tem o mesmo nome em todas as rotas.
- **Mudança que quebra contrato é decisão registrada.** Enquanto não houver
  consumidor externo, quebrar é permitido — mas a spec que introduz a quebra
  precisa dizer o que quebrou e por quê.

## Artigo XII — Emendas

Esta constituição só muda por emenda explícita, que exige:

1. Um commit dedicado, que altera apenas este arquivo.
2. Justificativa no corpo da mensagem do commit.
3. Incremento da versão semântica no topo:
   - **MAJOR** — remoção ou inversão de um artigo.
   - **MINOR** — novo artigo ou nova regra vinculante.
   - **PATCH** — redação, exemplo, correção sem mudança de obrigação.
4. Revisão dos artefatos em `specs/` que dependiam do artigo alterado.

Código que contraria a constituição sem emenda correspondente é bug, mesmo que
os testes passem.
