# Pesquisa e decisões técnicas — Spec 002

Continua a numeração da Spec 001, que terminou na ADR-008.

---

## ADR-009 — A fonte aceita vários códigos numa chamada

**Contexto.** Todo o ganho de cota desta feature depende de a fonte aceitar
vários ativos por requisição. Se não aceitasse, "uma chamada só" seria
impossível e o FR-006 teria de virar "uma chamada por ativo faltante".

**Investigação.** A documentação da BRAPI descreve o parâmetro como
*"Ticker(s) de ativos separados por vírgula (ex: PETR4 ou PETR4,VALE3,ITUB4)"*,
e a geração v2 usa `?symbols=PETR4,VALE3`. As duas gerações aceitam.

Isso também explica um detalhe que estava à vista desde a Spec 001 e não tinha
sido notado: a resposta sempre veio com `results` como **lista**. O formato já
era de múltiplos; nós é que pedíamos um.

**Decisão.** Uma chamada só, com os códigos faltantes unidos por vírgula.

**Limite por chamada.** É limite de **plano**, não da API: a tabela de preços
declara 10 ativos por chamada no Startup e 20 no Pro. O plano gratuito não
publica o número. Por isso `MAX_TICKERS_PER_REQUEST` é configuração com padrão
3, e não constante (ver ADR-012 do plano e o Complexity Tracking).

**Verificação pendente.** O contract test com o token real é o que confirma o
teto do plano gratuito. Até lá, 3 é uma aposta conservadora, não um fato.

---

## ADR-010 — Portas plurais substituem as singulares

**Contexto.** Com a consulta múltipla, cada porta poderia ganhar um método novo
ao lado do antigo: `fetch` e `fetch_many`, `get` e `get_many`.

**Decisão.** As plurais **substituem** as singulares. A consulta de um ativo
passa a ser uma lista de um elemento.

**Justificativa.** O Artigo III (ISP) pede portas pequenas, e o VII proíbe
manter duas formas de fazer a mesma coisa. Duas assinaturas para a mesma
operação dobrariam a superfície de teste dos adapters e criariam a pergunta
"qual eu uso?" em todo ponto de chamada — sem que a resposta importasse.

**Consequência.** `fetch_many` devolve um mapa apenas com os **encontrados**.
Ausência no mapa é a informação de "não existe", o que evita inventar uma
exceção por item dentro de um lote. A rota de um ativo traduz essa ausência em
`QuoteNotFoundError`; a rota de coleção traduz em `status: notFound`.

**Alternativa descartada.** Manter `fetch` e implementá-lo chamando
`fetch_many`. Economizaria uma linha no caso de uso individual e custaria um
método a mais em toda implementação de porta, incluindo os dublês de teste.

---

## ADR-011 — Leitura e escrita do cache em lote

**Contexto.** Consultar o Redis uma vez por ativo transformaria a economia de
chamadas externas em três idas ao cache — trocaria um gargalo por outro.

**Decisão.** `get_many` usa `MGET`; `set_many` usa pipeline. Uma ida na leitura,
uma na escrita, independente da quantidade de ativos.

**TTL.** Continua por ativo (`CACHE_TTL_SECONDS`), aplicado individualmente
dentro do pipeline. Dois ativos pedidos juntos podem expirar em momentos
diferentes — é o que a spec descreve e o que evita invalidação em cascata.

**Degradação.** O contrato de robustez da porta continua valendo: falha do Redis
em `get_many` devolve mapa vazio (todos viram faltantes) e em `set_many` é
silenciosa. O caso de uso segue sem `try/except` de infraestrutura.

---

## ADR-012 — Não encontrado é resultado na coleção e ausência no item

**Contexto.** Com vários ativos numa requisição, um código bem formado que a
bolsa não conhece não pode derrubar os outros.

**Decisão.**
- Em `GET /ticker` (coleção): o ativo aparece na lista com `status: notFound` e
  `quote: null`. A requisição é `200`.
- Em `GET /ticker/{codigo}` (item): a ausência é `404`, como hoje.

**Justificativa.** Artigo XI. Numa coleção, "não achei este" é um resultado
legítimo da busca — a busca funcionou. Num item, o recurso pedido não existe, e
`404` é exatamente isso. Uniformizar as duas seria escolher um dos dois erros:
ou um `404` que apaga nove resultados bons, ou um `200` para um recurso
inexistente.

**Formato inválido é diferente.** Ele **não** entra na lista: derruba a
requisição inteira com `400`, antes de qualquer chamada externa. Código mal
formado é erro de quem chamou, não resultado de busca — e é a validação que
protege a cota (SC-005).

---

## ADR-013 — `Retry-After` é repassado, não obedecido em silêncio

**Contexto.** O FR-013 pede respeitar a sinalização de limite de uso da fonte.
A leitura literal — "aguarde o tempo indicado antes de insistir" — sugere um
retry dentro da requisição.

**Decisão.** Nenhum retry automático. Quando a fonte responde `429`, lemos o
`Retry-After` e o repassamos no cabeçalho do nosso `503`.

**Justificativa.** Um retry interno prenderia a conexão de quem chamou por
segundos, sem que ele tivesse pedido isso, e escondendo o motivo. Repassar o
cabeçalho entrega a mesma informação e devolve a decisão a quem pode tomá-la.
É também o que o Artigo VIII quer dizer com "erro é parte do contrato": a
resposta informa o que houve e o que fazer.

**Consequência.** Também passamos a ler `RateLimit-Remaining` para log
(Artigo IX), o que dá visibilidade do consumo de cota sem nenhuma chamada extra.

---

## ADR-014 — O mapper trabalha por código pedido, não por posição

**Contexto.** A resposta da fonte é uma lista. Casar pedido e resposta por
índice pareceria natural.

**Decisão.** O mapper indexa os itens recebidos pelo `symbol` de cada um e o
caso de uso procura por código. Posição é ignorada.

**Justificativa.** Nada garante que a fonte devolva os ativos na ordem pedida,
nem que devolva todos. Casar por posição produziria, no melhor caso, um erro
ruidoso e, no pior, a cotação de um ativo atribuída a outro — o tipo de defeito
que passa despercebido justamente porque a resposta parece válida.

**Consequência.** A ordem da resposta é responsabilidade **nossa**: o caso de
uso monta o resultado percorrendo os códigos na ordem em que foram pedidos
(FR-016), sem depender da fonte para isso.
