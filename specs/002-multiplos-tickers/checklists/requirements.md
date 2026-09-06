# Requirements Checklist: Consulta de múltiplos tickers com cache por ativo

**Purpose**: Revisão de qualidade dos requisitos da Spec 002 — clareza, completude e consistência do que foi especificado, antes de virar tarefa.
**Created**: 2026-09-06
**Feature**: [spec.md](../spec.md)

**Semântica dos marcadores**: `[x]` significa que o critério **de qualidade do
requisito** foi revisado e está satisfeito. Não significa implementação pronta.

## Completude

- [x] CHK001 Todo requisito funcional tem identificador estável (FR-001 a FR-017)
- [x] CHK002 Toda história de usuário tem prioridade declarada e justificativa da prioridade
- [x] CHK003 Toda história tem "Independent Test" — como verificá-la sozinha e que valor entrega isolada
- [x] CHK004 Existe seção de Success Criteria com resultados mensuráveis (SC-001 a SC-008)
- [x] CHK005 Existe seção de Assumptions com o que foi assumido sem confirmação
- [x] CHK006 Os cenários de borda cobrem lista vazia, repetição, excesso, falha parcial e cache fora do ar
- [x] CHK007 A quebra de contrato da rota antiga está declarada como requisito (FR-017), não implícita

> CHK002 a CHK005 eram as quatro lacunas registradas no checklist da Spec 001.
> Estão pagas nesta.

## Clareza

- [x] CHK008 A especificação descreve o quê e o porquê, sem nome de biblioteca
- [x] CHK009 Cada critério de aceite é observável de fora, sem inspecionar cache ou log
- [x] CHK010 Nenhum `[NEEDS CLARIFICATION]` permanece em aberto
- [x] CHK011 As quatro ambiguidades levantadas têm resposta registrada na sessão de clarificação
- [x] CHK012 O nome do parâmetro de consulta tem justificativa escrita, não só escolha

## Consistência

- [x] CHK013 Todo requisito funcional tem teste planejado na rastreabilidade do plano
- [x] CHK014 O contrato em `contracts/openapi.yaml` cobre as duas rotas e o item da lista
- [x] CHK015 O comportamento de "não encontrado" é coerente entre item (404) e coleção (status), e a diferença é justificada
- [x] CHK016 Nenhum requisito contradiz outro — em especial FR-007 (não chamar) e FR-006 (uma chamada)
- [x] CHK017 A spec não reintroduz `price` anulável, defeito corrigido na Spec 001

## Alinhamento constitucional

- [x] CHK018 Artigo X — o vocabulário é o do domínio: `ticker`, não `symbols` da fonte
- [x] CHK019 Artigo X — `Quote` continua Value Object puro; origem e status ficam na aplicação
- [x] CHK020 Artigo XI — item devolve objeto, coleção devolve lista inclusive com um elemento
- [x] CHK021 Artigo XI — filtro em parâmetro de consulta, não em segmento de caminho
- [x] CHK022 Artigo VII — o que foi deliberadamente não construído está registrado com motivo
- [x] CHK023 Artigo IV — todo FR tem teste que falharia se ele fosse violado

## Riscos reconhecidos e ainda abertos

Desmarcados de propósito: são incertezas que a especificação **não pode**
resolver sozinha, e que a implementação ou o contract test resolvem.

- [ ] CHK024 O teto real de ativos por chamada no plano gratuito está confirmado
      *(a documentação da fonte publica 10 no Startup e 20 no Pro, mas não o do gratuito; só o contract test com o token real confirma)*
- [ ] CHK025 O comportamento da fonte quando um dos códigos do lote não existe está confirmado
      *(a spec assume que ela simplesmente omite o ausente de `results`; a alternativa — devolver o lote inteiro com erro — mudaria o FR-011)*

## Notas

- CHK017 existe porque esse defeito já aconteceu: na Spec 001 o `price` foi
  publicado como anulável num campo que nunca vem nulo, e só apareceu quando o
  teste passou a comparar tipos entre contrato e implementação.
- CHK024 e CHK025 são o motivo de o contract test ser parte da definição de
  pronto desta feature, e não um extra.
