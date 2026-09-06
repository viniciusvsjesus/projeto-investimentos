# Feature Specification: Consulta de múltiplos tickers com cache por ativo

**Feature Branch**: `002-multiplos-tickers`

**Created**: 2026-09-06

**Status**: Clarificada — pronta para `/speckit-plan`

**Input**: User description: "alterar o endpoint /cotacao/ para /ticker, receber 2 ou 3 tickers por vez em vez de 1, e sempre consultar o cache separadamente por ticker antes de bater na API, para não gastar requisição à toa"

## Clarifications

### Session 2026-09-06

- Q: Os ativos vão no caminho ou em parâmetro de consulta? → A: Duas rotas
  distintas. `GET /ticker/{codigo}` continua devolvendo **um objeto** para um
  ativo. `GET /ticker` passa a receber uma lista por parâmetro de consulta
  repetido e devolve **uma lista**.
- Q: Qual o nome do parâmetro de consulta? → A: Decisão delegada, com o critério
  de coerência e boas práticas. Escolhido `ticker`, repetido:
  `GET /ticker?ticker=ITSA4&ticker=PETR4`. É a palavra do nosso domínio — o
  Value Object se chama `Ticker` e o caminho já é `/ticker` — e **não** é a
  palavra da fonte externa, que usa `symbols`. O Artigo XI proíbe vocabulário de
  fonte externa vazar para o nosso contrato, e o Artigo X manda usar a linguagem
  ubíqua do domínio. `valor` e `id` foram descartados por não dizerem o que são.
- Q: Qual o limite de ativos por requisição? → A: Máximo 3, que é o teto do plano
  gratuito da fonte, configurável por variável de ambiente.
- Q: O que acontece quando parte dos ativos falha? → A: Código com formato
  inválido derruba a requisição inteira com `400`, sem gastar chamada externa.
  Código bem formado que a bolsa não conhece volta **dentro** da resposta,
  marcado como não encontrado, junto dos que deram certo.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consultar vários ativos numa chamada (Priority: P1)

**Como** aplicação consumidora, **quero** pedir a cotação de vários ativos numa
única requisição, **para** montar a visão de uma carteira sem fazer uma ida e
volta por papel.

**Why this priority**: é a capacidade central da feature. Sem ela, nada mais
desta spec tem razão de existir — as demais histórias otimizam ou renomeiam algo
que só passa a valer a pena quando a consulta múltipla existe.

**Independent Test**: pedir três códigos válidos numa requisição e receber as
três cotações, cada uma com preço, moeda e instante. Entrega valor sozinha,
mesmo sem cache e mesmo mantendo o nome antigo da rota.

**Acceptance Scenarios**:

1. **Given** três códigos válidos e negociados, **When** `GET /ticker` é chamado
   com os três, **Then** a resposta é uma lista com as três cotações.
2. **Given** um único código válido, **When** `GET /ticker` é chamado com ele,
   **Then** a resposta é uma lista de um elemento — coleção não muda de forma
   por causa da quantidade.
3. **Given** o mesmo código repetido na requisição, **When** a consulta é feita,
   **Then** ele é resolvido uma vez só e aparece uma vez na resposta.
4. **Given** a ordem em que os códigos foram pedidos, **When** a resposta é
   montada, **Then** ela preserva essa ordem.

---

### User Story 2 - Não gastar cota com o que já está em cache (Priority: P2)

**Como** dono da cota da fonte externa, **quero** que cada ativo seja procurado
no cache individualmente, **para** que só os ausentes sejam buscados e a cota
não seja consumida por dado que já temos.

**Why this priority**: é o motivo econômico da feature, mas depende da US1
existir. Sem esta história a consulta múltipla funciona — só desperdiça cota
buscando o que já estava em casa.

**Independent Test**: aquecer o cache com um ativo, pedir dois (o aquecido e um
novo) e verificar que a fonte externa foi chamada apenas com o novo. Verificável
de fora, sem inspecionar o cache.

**Acceptance Scenarios**:

1. **Given** dois ativos pedidos e um deles já em cache dentro da janela de
   validade, **When** a consulta é feita, **Then** a fonte externa é chamada
   apenas com o ativo ausente.
2. **Given** todos os ativos pedidos já em cache, **When** a consulta é feita,
   **Then** a fonte externa **não** é chamada nenhuma vez.
3. **Given** nenhum dos ativos em cache, **When** a consulta é feita, **Then** a
   fonte externa é chamada **uma vez só**, com todos eles — não uma vez por ativo.
4. **Given** ativos buscados na fonte, **When** a resposta é montada, **Then**
   cada cotação é gravada no cache individualmente, com validade própria.
5. **Given** uma resposta montada, **When** ela é devolvida, **Then** cada ativo
   informa se veio do cache ou da fonte.

---

### User Story 3 - Rota que nomeia o recurso (Priority: P3)

**Como** desenvolvedor consumindo a API, **quero** que o caminho nomeie o
recurso consultado, **para** entender a URL sem consultar a documentação.

**Why this priority**: melhora a clareza da interface, mas não muda o que o
sistema faz. É a última em valor e a primeira a ser descartada se o escopo
apertar.

**Independent Test**: chamar `GET /ticker/PETR4` e receber a cotação de um
ativo; chamar `GET /cotacao/PETR4` e receber a resposta prevista para caminho
inexistente.

**Acceptance Scenarios**:

1. **Given** o serviço no ar, **When** `GET /ticker/PETR4` é chamado, **Then** a
   resposta é **um objeto** com a cotação — não uma lista.
2. **Given** o serviço no ar, **When** `GET /cotacao/PETR4` é chamado, **Then** a
   resposta é a de recurso inexistente, sem erro interno.
3. **Given** o índice em `/`, **When** ele é consultado, **Then** ele anuncia as
   duas rotas novas e não a antiga.

### Edge Cases

- **Nenhum ativo informado**: `GET /ticker` sem nenhum parâmetro é rejeitado
  como entrada inválida, sem chamada externa.
- **Código com formato inválido junto de válidos**: `400` para a requisição
  inteira, sem chamada externa (FR-011).
- **Ativo válido mas inexistente na bolsa**: aparece na lista marcado como não
  encontrado, ao lado dos que resolveram (FR-011).
- **Mais ativos do que o limite**: `400` explicando o limite, sem chamada externa.
- **Códigos repetidos**: resolvidos uma vez só, contados uma vez só no limite.
- **Diferença entre pedido e resposta da fonte**: se forem pedidos três ativos e
  a fonte devolver dois, o ausente é tratado como não encontrado — nunca como
  cotação vazia ou preço zero.
- **Cache indisponível**: a consulta segue direto para a fonte com todos os
  ativos pedidos, sem falhar.
- **Fonte fora do ar com parte dos ativos em cache**: os que estavam em cache
  são devolvidos; os que dependiam da fonte são marcados como indisponíveis.
- **Diferença de maiúsculas entre os pedidos**: `petr4` e `PETR4` na mesma
  requisição são o mesmo ativo e contam como um.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE aceitar de um até o limite configurado de códigos numa única requisição a `GET /ticker`.
- **FR-002**: O sistema DEVE validar o formato de cada código **antes** de qualquer chamada externa.
- **FR-003**: O sistema DEVE normalizar os códigos para maiúsculas e remover repetições antes de processar.
- **FR-004**: O sistema DEVE consultar o cache **individualmente para cada ativo**, e não para o conjunto.
- **FR-005**: O sistema DEVE chamar a fonte externa apenas com os ativos ausentes do cache.
- **FR-006**: O sistema DEVE agrupar todos os ativos ausentes em uma **única** chamada à fonte, não uma por ativo.
- **FR-007**: O sistema NÃO DEVE chamar a fonte externa quando todos os ativos pedidos estiverem em cache.
- **FR-008**: O sistema DEVE gravar cada cotação obtida no cache individualmente, com validade própria por ativo.
- **FR-009**: O sistema DEVE informar, por ativo, se a cotação veio do cache ou da fonte.
- **FR-010**: O sistema DEVE recusar requisições acima do limite de ativos por chamada, com limite configurável por ambiente e padrão **3** — o teto do plano gratuito da fonte.
- **FR-011**: O sistema DEVE rejeitar a requisição inteira com `400` quando **qualquer** código tiver formato inválido, sem chamada externa; e DEVE devolver, dentro da lista de resultados, marcação de não encontrado para código bem formado que a fonte não conhece.
- **FR-012**: O sistema DEVE expor duas rotas: `GET /ticker/{codigo}`, que devolve **um objeto**, e `GET /ticker`, que recebe o parâmetro de consulta `ticker` repetido e devolve **uma lista**.
- **FR-013**: O sistema DEVE respeitar a sinalização de limite de uso da fonte, aguardando o tempo que ela indicar antes de insistir.
- **FR-014**: O sistema DEVE continuar atendendo quando o cache estiver indisponível, buscando todos os ativos na fonte.
- **FR-015**: O sistema DEVE manter, para cada ativo, o mesmo conjunto de campos que a consulta individual já devolve hoje.
- **FR-016**: O sistema DEVE preservar, na lista de resposta, a ordem em que os ativos foram pedidos.
- **FR-017**: O sistema DEVE deixar de atender a rota `/cotacao/{ticker}`.

### Key Entities

- **Ativo**: o código de negociação. Já existe, com regra de formato própria.
  Passa a ser elemento de uma coleção, não mais valor único da requisição.
- **Cotação**: o retrato de preço de um ativo num instante. Não muda.
- **Consulta de cotações**: novo agrupador. Reúne os ativos pedidos, as cotações
  resolvidas, os não encontrados e, para cada resolvida, a origem — cache ou
  fonte. É o que permite o FR-009 e o FR-011 sem contaminar a cotação com
  metadado de infraestrutura, respeitando o Artigo X.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Uma consulta com N ativos resulta em **no máximo uma** chamada à fonte externa, qualquer que seja N dentro do limite.
- **SC-002**: Uma consulta em que todos os ativos estão em cache resulta em **zero** chamadas à fonte externa.
- **SC-003**: Consultar três ativos numa requisição consome **um terço** das requisições de cota que três consultas separadas consumiriam.
- **SC-004**: Um ativo já em cache **nunca** aparece na chamada à fonte, mesmo quando pedido junto de ativos ausentes.
- **SC-005**: Um código com formato inválido é rejeitado com **zero** chamadas à fonte.
- **SC-006**: A resposta permite, sem consultar log nem cache, dizer de qual origem veio cada ativo e quais não foram encontrados.
- **SC-007**: Toda a suíte de testes continua passando sem rede, com a fonte externa simulada.
- **SC-008**: Nenhum nome de campo ou parâmetro da nossa API coincide com o vocabulário da fonte externa por acidente — `ticker` é palavra nossa, `symbols` é dela.

## Assumptions

- A rota antiga é **substituída**, não mantida como apelido. Hoje o único
  consumidor é o autor do projeto, então não há contrato externo a preservar —
  e o Artigo XI exige que a quebra fique registrada, o que o FR-017 faz.
- O conjunto de campos de cada cotação continua o mesmo de hoje; esta feature
  muda quantos ativos cabem numa requisição, não o que se sabe de cada um.
- A validade do cache continua contada por ativo, de forma independente — dois
  ativos pedidos juntos podem expirar em momentos diferentes.
- A fonte externa aceita vários códigos separados por vírgula numa chamada. Está
  documentado por ela (`PETR4,VALE3,ITUB4`) e é o que torna o FR-006 possível; o
  teste de contrato confirma contra a API real.
- O limite de 3 ativos vem do plano gratuito. A documentação pública da fonte
  declara 10 no plano Startup e 20 no Pro, mas não publica o número do gratuito
  — por isso o valor é configurável, e não constante.
- Continua sem autenticação na nossa API, como decidido na Spec 001.
