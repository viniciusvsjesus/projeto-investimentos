# Plano de Implementação: <NOME DA FEATURE>

- **Spec de origem:** `specs/<NNN-slug>/spec.md`
- **Data:** <AAAA-MM-DD>

## 1. Portão constitucional (pré-implementação)

| Artigo | Verificação | Situação |
|---|---|---|
| II — Hexagonal | A dependência aponta só para dentro? | ⬜ |
| III — SOLID | Portas pequenas, DIP respeitado? | ⬜ |
| IV — Teste antes | Todo RF tem teste planejado? | ⬜ |
| V — Segredos | Nenhum segredo versionado? | ⬜ |
| VI — Docker | Sobe com um comando só? | ⬜ |
| VII — Simplicidade | Alguma abstração especulativa? | ⬜ |
| VIII — Erros | Todo erro mapeado para status HTTP? | ⬜ |

**Bloqueio:** nenhuma tarefa de implementação começa com item em ⬜.

## 2. Stack e versões

Cada escolha traz a alternativa descartada e o motivo (detalhe em `research.md`).

## 3. Estrutura de diretórios

Árvore de arquivos com a camada hexagonal de cada um.

## 4. Portas e adapters

| Porta | Direção | Assinatura | Implementações |
|---|---|---|---|

## 5. Fluxo de uma requisição

Passo a passo, da borda ao núcleo e de volta.

## 6. Mapeamento de erros

| Exceção de domínio | HTTP | Corpo |
|---|---|---|

## 7. Complexity Tracking (Artigo VII)

| Complexidade introduzida | Por quê é necessária | Alternativa mais simples e por que não serve |
|---|---|---|

## 8. Rastreabilidade

| Requisito | Artefato de projeto | Teste |
|---|---|---|
