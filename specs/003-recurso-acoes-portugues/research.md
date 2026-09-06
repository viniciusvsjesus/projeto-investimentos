# Pesquisa e decisões técnicas — Spec 003

Continua a numeração das Specs 001 e 002, que terminaram na ADR-014.

---

## ADR-015 — O recurso é nomeado pelo dado, e a coleção é plural

**Contexto.** `/ticker?ticker=ITSA4` repete a mesma palavra como recurso e como
filtro, e nenhum dos dois é o que a rota devolve. O autor levantou o problema e
propôs `/acao/ITSA4` para um ativo e `/acoes?…` para vários, afirmando estar no
padrão REST.

**Investigação.** Os guias consultados convergem em dois pontos:

- **Coleção no plural, item dentro dela.** "Use the plural name to denote the
  collection resource archetype"; "Collections are usually plural (e.g.
  `/posts`), while resources are identified with a unique identifier (e.g.
  `/posts/abc1`)".
- **Filtro em parâmetro de consulta sobre a própria coleção**, em vez de rotas
  separadas: "enable sorting, filtering, and pagination capabilities in resource
  collection API and pass the input parameters as query parameters".

**Decisão.** Uma raiz só: `GET /acoes` (coleção) e `GET /acoes/{ticker}` (item).

**Por que não `/acao` e `/acoes`.** Seriam dois recursos com nomes diferentes
para a mesma coisa. Um consumidor que conhecesse um não teria como deduzir o
outro, e a relação item-coleção — que é o que o padrão codifica — se perderia.

**Por que não `/quotes` (ou `/cotacoes`).** Foi a primeira proposta e o autor
recusou por soar estranho. `acoes` cumpre o mesmo requisito: nomeia o **dado**
devolvido, não o identificador.

**Nome do filtro.** `ticker`, não `codigo`. É a palavra corrente do mercado
brasileiro, é o nome do Value Object do domínio (Artigo X) e é específica —
"código" seria genérico. E a redundância desapareceu, porque o recurso agora se
chama `acoes`.

---

## ADR-016 — Português é decisão de contrato, não de implementação

**Contexto.** O projeto mistura línguas: specs, commits e constituição em
português; caminho e payload em inglês. O autor escolheu unificar em português.

**Decisão.** Só a **borda** fala português. `domain/` e `application/` seguem em
inglês, e a tradução acontece por alias do Pydantic em `schemas.py`.

**Justificativa.** O Artigo X manda usar a linguagem ubíqua do domínio, e a
linguagem em que este código é escrito é o inglês — `Ticker`, `Quote`,
`QuoteResolution`. Renomear para `Cotacao` e `Resolucao` produziria um híbrido
(`self._cache.get_many` devolvendo `Cotacao`) sem trazer ganho algum a quem
consome a API. O consumidor vê a resposta, não o nome da classe.

**Consequência.** O diff desta feature é quase todo em `schemas.py`. É o mesmo
lugar onde a Spec 001 já traduzia `regularMarketPrice` para `price` — só que
agora a tradução tem dois saltos: BRAPI → domínio → contrato.

**O que não é traduzido.** `ticker` e `volume`, idênticos nas duas línguas; e os
campos do corpo de erro, pela ADR-017.

---

## ADR-017 — O corpo de erro continua em RFC 9457

**Contexto.** O FR-006, lido ao pé da letra, mandaria traduzir `type`, `title`,
`status`, `detail` e `instance`.

**Decisão.** Não traduzir. Os **valores** continuam em português; os **nomes**
seguem o RFC 9457.

**Justificativa.** Esses nomes não são escolha nossa. A API declara
`Content-Type: application/problem+json`, e é esse padrão que permite a um
cliente genérico entender um erro de qualquer API sem ler documentação.
Traduzir os campos produziria um corpo que **declara** ser problem+json sem o
ser — pior que não declarar nada.

A parte destinada a humanos — `title` e `detail` — já está em português desde a
Spec 001. O erro já fala português onde isso importa.

**Registro.** Divergência descoberta na fase de plano, com a spec ajustada em
seguida. É o Artigo VIII prevalecendo sobre consistência cosmética.

---

## ADR-018 — A validade anunciada é a restante, medida pelo Redis

**Contexto.** O FR-009 exige `max-age` com o tempo **restante**. Anunciar o TTL
configurado seria mentir: uma cotação que entrou no cache há 45 segundos com TTL
de 60 vale 15, não 60 — e um consumidor que confiasse no número serviria dado
vencido por 45 segundos.

**Investigação.** O cliente `redis-py` expõe `TTL` e `PTTL`. Num pipeline,
`GET` e `TTL` de cada chave viajam na **mesma ida** ao servidor — a leitura
continua sendo uma só, como a ADR-011 exige.

**Decisão.** `get_many` passa a devolver `CachedQuote(quote, ttl_seconds)`. O
tipo vive junto da porta, porque validade é assunto do cache.

**Normalização.** O Redis devolve `-1` para chave sem expiração e `-2` para
chave inexistente. Qualquer valor não positivo vira **ausência de validade** no
adapter — nunca um `max-age` negativo ou eterno escapando para a resposta.

**Cotação vinda da fonte.** Recebe o TTL cheio, porque acabou de ser gravada. O
caso de uso recebe esse número por injeção, do mesmo jeito que já recebe o
limite de ativos.

**Cache desligado.** O container injeta validade zero, e a borda emite
`no-store`. Sem cache, não há validade a prometer.

---

## ADR-019 — Na lista, vence o menor `max-age`

**Contexto.** Uma resposta com três ativos pode ter três validades diferentes:
um do cache com 12 segundos restantes, outro com 50, outro recém-buscado com 60.

**Decisão.** O `max-age` da resposta é o **menor** entre os itens.

**Justificativa.** O cabeçalho descreve a **resposta inteira**, não cada item.
Anunciar 60 faria um proxy servir por 60 segundos uma lista cujo primeiro item
venceu aos 12. O menor é o único valor que nunca mente.

**Consequência aceita.** A lista é revalidada mais cedo do que a maioria dos
seus itens precisaria. É o preço de o HTTP cachear respostas, não elementos —
e é o lado seguro do erro.

**Sem cotação válida alguma.** `no-store`, pela ADR-018.
