# Requirements Checklist: Consulta de cotação de um ativo

**Purpose**: Revisão de qualidade dos requisitos da Spec 001 — clareza, completude e consistência do que foi especificado.
**Created**: 2026-09-06
**Feature**: [spec.md](../spec.md)

**Nota**: Este checklist foi escrito à mão durante a adoção do Spec Kit oficial,
para cobrir retroativamente a Spec 001, que foi construída antes da ferramenta
estar instalada. Das próximas em diante ele sai do `/speckit-checklist`.

**Semântica dos marcadores**: `[x]` significa que o critério **de qualidade do
requisito** foi revisado e está satisfeito. Não significa que a implementação
está pronta — isso é assunto do `tasks.md`.

## Completude

- [x] CHK001 Todo requisito funcional tem um identificador estável (RF-01 a RF-10)
- [x] CHK002 Todo requisito funcional aponta para a história de usuário ou o problema que o originou
- [x] CHK003 Todo critério de aceite é observável de fora do sistema, sem inspecionar estado interno
- [x] CHK004 O escopo fora do MVP está listado explicitamente, item a item
- [x] CHK005 Os cenários de erro cobrem falha da fonte externa, entrada inválida e indisponibilidade de dependência
- [x] CHK006 Os requisitos não funcionais têm métrica verificável, não adjetivo ("responde em até 8s", não "rápido")

## Clareza

- [x] CHK007 A especificação descreve o quê e o porquê, sem nome de biblioteca ou framework
- [x] CHK008 Cada regra de negócio está enunciada de forma testável (RN-01 a RN-06)
- [x] CHK009 Termos do domínio (ticker, cotação, fracionário) são usados de forma consistente
- [x] CHK010 Nenhum `[NEEDS CLARIFICATION]` permanece em aberto
- [x] CHK011 Toda ambiguidade levantada tem resposta registrada em `clarify.md` (Q1 a Q9)

## Consistência

- [x] CHK012 Todo requisito funcional tem ao menos um teste que falharia se ele fosse violado (rastreabilidade em `plan.md` §8)
- [x] CHK013 O contrato publicado em `contracts/openapi.yaml` bate com o que a implementação gera — verificado por teste
- [x] CHK014 O contrato consumido em `contracts/brapi-quote.md` reflete o payload real da fonte
- [x] CHK015 As decisões técnicas do `research.md` não contradizem nenhum artigo da constituição
- [x] CHK016 RN-01 (formato do código de ativo) cobre os casos reais da B3, incluindo dígito no prefixo (`B3SA3`) e BDRs (`M1TA34`)

## Lacunas em relação ao template oficial

Itens que o `spec-template.md` do Spec Kit pede e que a Spec 001 não tem, por
ter sido escrita antes da adoção da ferramenta. Ficam **desmarcados de
propósito** — são dívida reconhecida, não item esquecido.

- [ ] CHK017 Histórias de usuário priorizadas como P1/P2/P3, com justificativa da prioridade
- [ ] CHK018 Cada história com um "Independent Test" declarado — como testá-la isoladamente e que valor ela entrega sozinha
- [ ] CHK019 Seção "Success Criteria" com resultados mensuráveis e independentes de tecnologia
- [ ] CHK020 Seção "Assumptions" explicitando o que foi assumido sem confirmação

## Notas

- CHK016 nasceu de um defeito real: a regra original exigia quatro letras e
  reprovava `B3SA3`, um código legítimo. Foi um teste com o payload real da
  BRAPI que expôs.
- CHK013 também nasceu de defeito: o `price` era publicado como anulável num
  campo que nunca vem nulo. O teste que compara tipos entre contrato e
  implementação foi criado por causa disso.
- As lacunas CHK017 a CHK020 não bloqueiam a Spec 001, que já está entregue e
  em produção. Elas valem como critério para a Spec 002 em diante.
