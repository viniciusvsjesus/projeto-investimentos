# Spec 001 — Consulta de cotação de um ativo

- **ID:** 001-cotacao-ticker
- **Status:** Aprovada
- **Autor:** Vini
- **Data:** 2026-09-03
- **Constituição aplicável:** v1.0.0

---

## 1. Problema

Consultar a cotação de um ativo da B3 hoje exige falar diretamente com a BRAPI,
uma API externa. Isso empurra três problemas para dentro de cada aplicação que
precisa do dado:

1. **O token de acesso se espalha.** Cada consumidor precisa carregar a
   credencial da BRAPI, o que multiplica o risco de vazamento e torna a
   rotação do token uma operação de N sistemas.
2. **O contrato externo vaza para dentro.** O formato de resposta da BRAPI —
   nomes de campo, aninhamento, unidades — passa a ser o formato interno. Se a
   BRAPI mudar, todo mundo quebra junto.
3. **A cota gratuita é consumida sem controle.** Não existe um ponto único para
   aplicar cache, medir uso ou trocar o provedor de dados.

Sem uma camada própria entre a aplicação e a BRAPI, não há onde colocar cache,
tradução de contrato, tratamento de erro consistente nem controle de credencial.

## 2. Objetivo do MVP

Expor uma API HTTP própria que, dado o código de um ativo da B3, devolve a
cotação atual em um contrato JSON estável e independente da BRAPI.

## 3. Fora de escopo

Explicitamente **não** entram nesta entrega:

- Consulta de mais de um ativo na mesma requisição
- Série histórica de preços
- Dividendos, proventos e dados fundamentalistas
- Fundos imobiliários, criptomoedas, moedas, tesouro direto e opções
- Autenticação ou autorização na nossa API
- Persistência em banco de dados relacional
- Carteira, posição, rentabilidade ou qualquer cálculo financeiro
- Interface gráfica própria (o Swagger UI gerado atende a exploração manual)
- Múltiplos provedores de cotação simultâneos

Cada item acima é candidato a uma spec futura, não a um "já que estamos aqui".

## 4. Personas e histórias de usuário

**Persona única no MVP — Aplicação Consumidora:** qualquer serviço interno que
precise do preço atual de um ativo e não deve conhecer a BRAPI.

### US-01 — Obter a cotação atual de um ativo

**Como** aplicação consumidora,
**quero** consultar a cotação atual de um ativo pelo seu código de negociação,
**para** exibir ou calcular o valor de uma posição sem depender do contrato da BRAPI.

**Critérios de aceite**

- [ ] **CA-01.1** — Dado o código de um ativo existente e negociado na B3,
      quando a consulta é feita, então a resposta é `200` e contém o código, o
      nome do ativo, a moeda, o preço atual, a variação absoluta, a variação
      percentual, o volume negociado e o instante da cotação.
- [ ] **CA-01.2** — Dado um código de ativo com formato inválido, quando a
      consulta é feita, então a resposta é `400` e o corpo explica qual é o
      formato esperado, **sem** que a API externa seja chamada.
- [ ] **CA-01.3** — Dado um código com formato válido mas inexistente na B3,
      quando a consulta é feita, então a resposta é `404`.
- [ ] **CA-01.4** — Dado um código em letras minúsculas, quando a consulta é
      feita, então ele é tratado como equivalente ao mesmo código em maiúsculas.
- [ ] **CA-01.5** — Dada uma segunda consulta ao mesmo ativo dentro da janela de
      cache, quando a consulta é feita, então a resposta é servida do cache e a
      API externa **não** é chamada novamente.

### US-02 — Verificar a saúde do serviço

**Como** operador (ou o próprio Docker),
**quero** um endpoint de saúde,
**para** saber se o serviço e suas dependências estão em pé antes de mandar tráfego.

**Critérios de aceite**

- [ ] **CA-02.1** — Quando o serviço está no ar, então `/health` responde `200`
      com o estado do próprio serviço e o do cache.
- [ ] **CA-02.2** — Quando o cache está indisponível, então `/health` sinaliza a
      degradação, mas a consulta de cotação **continua funcionando**.

### US-03 — Consultar direto do navegador, sem ferramenta externa

**Como** desenvolvedor que acabou de subir o projeto,
**quero** colar uma URL no navegador e ver o JSON da cotação,
**para** validar a instalação sem instalar cliente HTTP nenhum e sem passar por
tela intermediária.

**Critérios de aceite**

- [ ] **CA-03.1** — Dado o serviço no ar, quando a raiz `/` é aberta no
      navegador, então a resposta é JSON identificando o serviço, seu estado e a
      URL de exemplo para consultar uma cotação.
- [ ] **CA-03.2** — Dada a URL de exemplo devolvida pela raiz, quando ela é
      aberta no navegador, então o JSON da cotação aparece direto — sem tela,
      sem botão e sem passo intermediário.

## 5. Requisitos funcionais

| ID | Requisito | Prioridade | Origem |
|---|---|---|---|
| RF-01 | O sistema DEVE expor a rota `GET /cotacao/{ticker}`, que recebe o código de um ativo e devolve sua cotação atual em JSON | Obrigatório | US-01 |
| RF-02 | O sistema DEVE validar o formato do código antes de qualquer chamada externa | Obrigatório | CA-01.2 |
| RF-03 | O sistema DEVE normalizar o código para maiúsculas | Obrigatório | CA-01.4 |
| RF-04 | O sistema DEVE traduzir a resposta da fonte externa para um contrato próprio e estável | Obrigatório | Problema #2 |
| RF-05 | O sistema DEVE armazenar a cotação em cache por uma janela configurável e servir do cache dentro dela | Obrigatório | CA-01.5 |
| RF-06 | O sistema DEVE continuar atendendo cotações quando o cache estiver indisponível | Obrigatório | CA-02.2 |
| RF-07 | O sistema DEVE expor um endpoint de saúde reportando o serviço e o cache | Obrigatório | US-02 |
| RF-08 | O sistema DEVE responder na raiz com um índice em JSON contendo o estado do serviço e a URL de exemplo de consulta | Obrigatório | CA-03.1 |
| RF-09 | O sistema DEVE publicar a especificação OpenAPI da própria API | Obrigatório | US-03 |
| RF-10 | O sistema DEVE responder com corpo de erro padronizado em todas as falhas | Obrigatório | Artigo VIII |

## 6. Requisitos não funcionais

| ID | Requisito | Métrica verificável |
|---|---|---|
| RNF-01 | Subida em qualquer máquina com Docker | `docker compose up -d` e o serviço responde, sem passo manual adicional |
| RNF-02 | Credencial da fonte externa nunca versionada nem exposta | `git log -p` não contém token; token ausente de logs, respostas e URLs |
| RNF-03 | Resposta servida do cache não depende da fonte externa | Teste comprova ausência de chamada externa no segundo acesso |
| RNF-04 | Falha da fonte externa não derruba o serviço | Timeout configurável; resposta `502`/`503` com corpo padronizado |
| RNF-05 | Núcleo de domínio isenta de framework | `domain/` importa apenas biblioteca padrão do Python |
| RNF-06 | Suíte de testes roda sem rede | Testes de unidade e integração passam offline |
| RNF-07 | Log de toda chamada externa | Ticker, latência e desfecho registrados; token nunca |
| RNF-08 | Configuração por ambiente | Nenhum valor de ambiente fixo no código ou na imagem |

## 7. Regras de negócio

| ID | Regra |
|---|---|
| RN-01 | Código de ativo válido segue o padrão da B3: quatro caracteres de prefixo — o primeiro sempre letra, os três seguintes letra ou dígito — mais um ou dois dígitos e sufixo `F` opcional para o mercado fracionário (ex.: `PETR4`, `B3SA3`, `BOVA11`, `MXRF11`, `AAPL34`, `PETR4F`) |
| RN-02 | O código é sempre normalizado para maiúsculas antes de qualquer uso |
| RN-03 | Valores monetários são representados com precisão decimal exata — nunca ponto flutuante binário |
| RN-04 | O instante da cotação é o informado pela fonte, em UTC, e não o instante da nossa requisição |
| RN-05 | A janela de cache é configurável e vale por ativo, de forma independente |
| RN-06 | Cache indisponível degrada o desempenho, nunca a disponibilidade |

## 8. Cenários de erro

| Situação | Comportamento esperado | Status |
|---|---|---|
| Código com formato inválido | Rejeita antes de chamar a fonte externa; corpo explica o formato | `400` |
| Código válido, ativo inexistente | Informa que o ativo não foi encontrado | `404` |
| Fonte externa rejeita a credencial | Não vaza detalhe da credencial; registra o incidente em log | `502` |
| Fonte externa estourou a cota | Sinaliza indisponibilidade temporária | `503` |
| Fonte externa lenta além do limite | Aborta pelo timeout configurado | `504` |
| Fonte externa devolve payload inesperado | Trata como falha de contrato, não como cotação vazia | `502` |
| Cache indisponível | Consulta segue direto na fonte externa | `200` |

## 9. Pontos em aberto

Nenhum pendente. Os pontos levantados durante a especificação foram resolvidos
na entrevista de clarificação e estão registrados em `clarify.md`.

## 10. Definição de pronto

- [ ] Todos os critérios de aceite (CA-01.x, CA-02.x, CA-03.x) cobertos por teste automatizado
- [ ] Nenhum `[NEEDS CLARIFICATION]` pendente
- [ ] Portão constitucional do `plan.md` inteiramente verde
- [ ] `docker compose up -d` sobe o serviço numa máquina limpa
- [ ] Nenhum segredo no repositório
