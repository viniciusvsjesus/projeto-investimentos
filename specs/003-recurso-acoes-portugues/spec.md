# Feature Specification: Recurso `acoes`, contrato em português e validade na resposta

**Feature Branch**: `003-recurso-acoes-portugues`

**Created**: 2026-09-06

**Status**: Clarificada — pronta para `/speckit-plan`

**Input**: User description: "melhorar o endpoint com as melhores práticas — `/ticker?ticker=` é esquisito, quero no estilo do recurso nomeado pelo dado, com nome em português; tudo em português; Cache-Control na resposta; sem versão no caminho"

## Clarifications

### Session 2026-09-06

- Q: Qual formato de URL? → A: O recurso passa a ser nomeado pelo **dado que
  devolve**, não pelo identificador — e em português. Some a redundância de
  `/ticker?ticker=`.
- Q: `/acao/ITSA4` e `/acoes?…`, como o autor propôs? → A: **Não.** Uma raiz só,
  no plural: `GET /acoes/ITSA4` para um ativo e `GET /acoes?ticker=…` para
  vários. Ver "Divergência resolvida" abaixo — o autor invocou o padrão REST, e
  o padrão diz coleção no plural com o item **dentro** dela, não duas raízes com
  nomes diferentes para a mesma coisa.
- Q: Nome do parâmetro de filtro? → A: `ticker`. Não há redundância, porque o
  recurso agora se chama `acoes`. Escolhido em vez de `codigo` porque "ticker" é
  vocabulário corrente do mercado brasileiro e é o nome do Value Object do nosso
  domínio (Artigo X), enquanto "código" é genérico — código de quê?
- Q: A API fala português ou inglês? → A: **Tudo em português**, rota e campos.
  Hoje mistura: caminho em inglês e payload em inglês, mas specs, commits e
  constituição em português.
- Q: Cache HTTP na resposta? → A: **Apenas `Cache-Control`**, sem `ETag` nem
  `304`. Metade do ganho com uma fração do código: navegador e proxy param de
  repetir a chamada dentro da janela de validade.
- Q: Versão no caminho (`/v1/`)? → A: **Não.** Versionar por mudança enquanto não
  houver consumidor externo, como o Artigo XI permite e o VII recomenda.

### Divergência resolvida

O autor propôs `/acao/ITSA4` (singular) para um ativo e `/acoes?…` (plural) para
vários, afirmando estar no padrão de nomenclatura REST.

A convenção é outra, e a diferença importa: **a coleção é plural e o item vive
dentro dela**. `/acoes` é a coleção; `/acoes/ITSA4` é um item *daquela* coleção.
Duas raízes distintas — `/acao` e `/acoes` — seriam dois recursos com nomes
diferentes para a mesma coisa, e um consumidor não teria como deduzir uma a
partir da outra.

Adotado `/acoes/{ticker}` e `/acoes`. Se o autor preferir a forma que propôs,
é uma linha de rota — mas ela deixa de poder ser chamada de padrão.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - URL que descreve o que devolve (Priority: P1)

**Como** desenvolvedor consumindo a API, **quero** um caminho que nomeie o dado
retornado e não repita o nome do filtro, **para** ler a URL e entender o que vem
sem consultar documentação.

**Why this priority**: é a queixa que originou a spec. `/ticker?ticker=ITSA4`
repete a mesma palavra em dois papéis diferentes — recurso e filtro — e nenhum
dos dois é o dado devolvido.

**Independent Test**: chamar `/acoes/ITSA4` e receber um objeto; chamar
`/acoes?ticker=ITSA4&ticker=PETR4` e receber uma lista. Entrega valor sozinha,
mesmo sem tradução e sem cache HTTP.

**Acceptance Scenarios**:

1. **Given** o serviço no ar, **When** `GET /acoes/ITSA4`, **Then** a resposta é
   **um objeto** com a cotação.
2. **Given** o serviço no ar, **When** `GET /acoes?ticker=ITSA4&ticker=PETR4`,
   **Then** a resposta é **uma lista** de dois elementos, na ordem pedida.
3. **Given** o serviço no ar, **When** `GET /ticker/ITSA4` ou `GET /ticker?…`,
   **Then** a resposta é a de recurso inexistente.
4. **Given** a coleção, **When** um único ativo é pedido em `/acoes`, **Then** a
   resposta continua sendo lista.

---

### User Story 2 - Contrato inteiramente em português (Priority: P2)

**Como** autor do projeto, **quero** que a API fale a mesma língua das specs, dos
commits e da constituição, **para** não ter de traduzir mentalmente a cada
leitura.

**Why this priority**: coerência tem valor real de manutenção, mas nenhuma
funcionalidade muda. Depende da US1 já ter definido os caminhos.

**Independent Test**: pedir uma cotação e verificar que nenhum nome de campo
está em inglês.

**Acceptance Scenarios**:

1. **Given** uma consulta bem-sucedida, **When** a resposta é lida, **Then**
   todos os nomes de campo estão em português.
2. **Given** uma consulta a vários ativos, **When** a resposta é lida, **Then**
   o campo de situação usa valores em português.
3. **Given** um erro, **When** o corpo é lido, **Then** ele continua no formato
   único de erro, com os nomes de campo em português.

---

### User Story 3 - A resposta diz por quanto tempo ainda vale (Priority: P3)

**Como** aplicação consumidora, **quero** saber a validade restante da cotação,
**para** não repetir a consulta dentro de uma janela em que a resposta não mudou.

**Why this priority**: estende ao consumidor a mesma economia que a Spec 002 deu
à fonte externa. Valiosa, mas nenhuma das outras histórias depende dela.

**Independent Test**: consultar duas vezes e verificar que o `max-age` da
segunda é menor que o da primeira, refletindo o tempo já decorrido.

**Acceptance Scenarios**:

1. **Given** uma cotação recém-buscada da fonte, **When** a resposta é
   devolvida, **Then** ela traz `Cache-Control` com a validade cheia.
2. **Given** uma cotação servida do cache há algum tempo, **When** a resposta é
   devolvida, **Then** o `max-age` reflete o tempo **restante**, não o total.
3. **Given** uma consulta a vários ativos com validades diferentes, **When** a
   resposta é devolvida, **Then** o `max-age` é o **menor** entre eles — a lista
   inteira deixa de valer quando o primeiro item vence.
4. **Given** uma resposta de erro, **When** ela é devolvida, **Then** não traz
   `Cache-Control` de validade positiva.

### Edge Cases

- **Consulta em que nenhum ativo foi encontrado**: a lista volta vazia de
  cotações, mas com os itens marcados. Qual validade anunciar? Ver FR-012.
- **Cache desligado** (`REDIS_URL` vazia): não há validade a informar.
- **Cotação servida da fonte**: validade cheia, porque acabou de entrar no cache.
- **Lista com um item do cache e outro da fonte**: vence o menor.
- **Rota antiga `/ticker`**: deixa de existir, como `/cotacao` deixou na Spec 002.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE expor `GET /acoes/{ticker}`, devolvendo **um objeto**.
- **FR-002**: O sistema DEVE expor `GET /acoes`, com o parâmetro `ticker` repetido, devolvendo **uma lista**.
- **FR-003**: O sistema DEVE deixar de atender `/ticker/{ticker}` e `/ticker`.
- **FR-004**: O sistema DEVE nomear todos os campos de resposta em português.
- **FR-005**: O sistema DEVE usar valores em português no campo de situação de cada item da lista.
- **FR-006**: O sistema DEVE manter o corpo único de erro com os nomes de campo do RFC 9457 (`type`, `title`, `status`, `detail`, `instance`) e os **valores** em português. Ajustado durante o plano: traduzir os nomes produziria um corpo que declara ser `application/problem+json` sem o ser, e um consumidor genérico de erro deixaria de entendê-lo.
- **FR-007**: O sistema DEVE preservar o significado de cada campo — esta feature renomeia, não muda o que se sabe de cada ativo.
- **FR-008**: O sistema DEVE informar `Cache-Control` com a validade restante da cotação em respostas bem-sucedidas.
- **FR-009**: O sistema DEVE calcular o `max-age` a partir do tempo **restante** de cada cotação, não do TTL configurado.
- **FR-010**: O sistema DEVE usar o menor `max-age` entre os itens quando a resposta for uma lista.
- **FR-011**: O sistema NÃO DEVE anunciar validade positiva em respostas de erro.
- **FR-012**: O sistema DEVE anunciar `no-store` quando não houver cotação alguma a cachear.
- **FR-013**: O sistema DEVE manter o índice da raiz anunciando as rotas vigentes.
- **FR-014**: O sistema NÃO DEVE introduzir prefixo de versão no caminho.

### Key Entities

Nenhuma entidade nova. Esta feature muda **nomes e cabeçalhos**, não o modelo.

O `Quote` do domínio permanece intacto — inclusive em inglês, porque o Artigo X
manda usar a linguagem ubíqua do domínio no código, e o código é escrito em
inglês. A tradução acontece na borda, que é exatamente onde a Spec 001 já
traduzia o vocabulário da BRAPI.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Nenhuma URL da API repete a mesma palavra como recurso e como filtro.
- **SC-002**: Zero nomes de campo em inglês em qualquer resposta da API.
- **SC-003**: Uma segunda consulta ao mesmo ativo, dentro da janela, pode ser evitada pelo consumidor apenas lendo o `Cache-Control` — sem chamar a API.
- **SC-004**: O `max-age` anunciado nunca é maior que a validade real restante da cotação.
- **SC-005**: Nenhuma resposta de erro é cacheável.
- **SC-006**: A suíte continua passando sem rede.
- **SC-007**: Nenhum comportamento das Specs 001 e 002 regride — cache por ativo, chamada única e falha parcial continuam como estão.

## Assumptions

- As rotas `/ticker` são **substituídas**, não mantidas como apelido. Continua
  sem consumidor externo, e o Artigo XI exige apenas que a quebra fique
  registrada — o FR-003 faz isso.
- O código-fonte continua em inglês. Português é decisão de **contrato**, não de
  implementação: renomear `Quote` para `Cotacao` misturaria a língua do domínio
  com a da borda e não traria ganho nenhum ao consumidor.
- O cálculo da validade restante depende de o cache informar quanto falta. Se
  isso não estiver disponível, a alternativa é anunciar o TTL cheio — o que
  violaria o SC-004 e será tratado no plano.
- `ETag` e `304` ficam fora por decisão explícita, não por esquecimento.
- Sem prefixo de versão, por decisão explícita.
