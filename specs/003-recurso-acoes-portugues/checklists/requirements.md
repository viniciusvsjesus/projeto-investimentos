# Requirements Checklist: Recurso `acoes`, contrato em português e validade

**Purpose**: Revisão de qualidade dos requisitos da Spec 003 antes de virarem tarefa.
**Created**: 2026-09-06
**Feature**: [spec.md](../spec.md)

**Semântica**: `[x]` = critério de qualidade do requisito revisado e satisfeito.
Não significa implementação pronta.

## Completude

- [x] CHK001 Todo FR tem identificador estável (FR-001 a FR-014)
- [x] CHK002 As três histórias têm prioridade, justificativa e teste independente
- [x] CHK003 Success Criteria são mensuráveis e independentes de tecnologia
- [x] CHK004 As premissas dizem o que foi decidido sem confirmar
- [x] CHK005 Os cenários de borda cobrem lista vazia, cache desligado, validades mistas e erro
- [x] CHK006 A quebra de contrato está declarada como requisito (FR-003), não implícita

## Clareza

- [x] CHK007 Nenhum `[NEEDS CLARIFICATION]` em aberto
- [x] CHK008 As seis perguntas da entrevista têm resposta registrada
- [x] CHK009 A divergência sobre `/acao` versus `/acoes` está documentada com a razão, não só com a decisão
- [x] CHK010 A escolha do nome do filtro (`ticker`, não `codigo`) tem justificativa escrita

## Consistência

- [x] CHK011 Todo FR tem teste planejado na rastreabilidade do plano
- [x] CHK012 O contrato em `contracts/openapi.yaml` cobre as duas rotas, o índice e a saúde
- [x] CHK013 Nenhum requisito contradiz outro
- [x] CHK014 O FR-006 foi ajustado quando o plano descobriu o conflito com o RFC 9457 — a spec não ficou mentindo
- [x] CHK015 A spec não reintroduz `preco` anulável, defeito corrigido na Spec 001
- [x] CHK016 SC-007 protege explicitamente o que as Specs 001 e 002 entregaram

## Alinhamento constitucional

- [x] CHK017 Artigo X — o domínio segue em inglês; a tradução fica na fronteira, com razão escrita
- [x] CHK018 Artigo XI — recurso nomeado pelo dado, coleção plural com o item dentro
- [x] CHK019 Artigo XI — filtro em parâmetro de consulta, não em segmento de caminho
- [x] CHK020 Artigo VIII — o corpo de erro continua padronizado e agora explicitamente RFC 9457
- [x] CHK021 Artigo VII — `ETag`, `/v1/` e negociação de conteúdo registrados como não construídos, com motivo

## Riscos ainda abertos

- [ ] CHK022 O `max-age` foi verificado contra o relógio, e não só contra o valor do TTL configurado
      *(o teste unitário usa um Redis de mentira; só o passo do quickstart com `sleep 20` prova que o número decresce de verdade)*
- [ ] CHK023 Nenhum consumidor externo depende de `/ticker`
      *(premissa: hoje só o autor consome; se isso mudar, o FR-003 vira quebra real)*

## Notas

- CHK014 registra algo que o processo pegou: o FR-006 pedia traduzir os campos
  do corpo de erro, e o plano descobriu que isso quebraria o
  `application/problem+json`. A spec foi corrigida antes de virar código.
- CHK022 é a diferença entre testar o cálculo e testar o comportamento. O
  primeiro está coberto; o segundo é o passo manual do quickstart.
