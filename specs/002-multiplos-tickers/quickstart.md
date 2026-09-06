# Quickstart — Spec 002

Roteiro de validação manual. Tudo pelo navegador; cada passo é colar uma URL e
olhar o JSON.

## Subir

```bash
docker compose up -d --build
```

O `--build` é necessário desta vez: a variável `MAX_TICKERS_PER_REQUEST` é nova.

## Validar

| Passo | URL | Esperado | Critério |
|---|---|---|---|
| 1 | `http://localhost:8000` | Índice anuncia `/ticker/{ticker}` e `/ticker`, não `/cotacao` | US3-3 |
| 2 | `http://localhost:8000/ticker/PETR4` | **Um objeto** com a cotação | US3-1 |
| 3 | `http://localhost:8000/cotacao/PETR4` | `404` — a rota antiga sumiu | US3-2, FR-017 |
| 4 | `http://localhost:8000/ticker?ticker=PETR4` | **Uma lista** de um elemento | US1-2 |
| 5 | `http://localhost:8000/ticker?ticker=ITSA4&ticker=PETR4&ticker=VALE3` | Lista com três, na ordem pedida | US1-1, FR-016 |
| 6 | Repetir o passo 5 na hora | Os três com `"cached": true` | US2-2, SC-002 |
| 7 | `http://localhost:8000/ticker?ticker=petr4&ticker=PETR4` | Lista de **um** elemento — repetição não duplica | US1-3 |
| 8 | `http://localhost:8000/ticker?ticker=PETR4&ticker=ZZZZ9` | PETR4 com `status: found`, ZZZZ9 com `status: notFound` e `quote: null` | FR-011 |
| 9 | `http://localhost:8000/ticker?ticker=PETR` | `400` — formato inválido derruba tudo | FR-011, SC-005 |
| 10 | `http://localhost:8000/ticker?ticker=A&ticker=B&ticker=C&ticker=D` (quatro válidos) | `400` explicando o limite | FR-010 |
| 11 | `http://localhost:8000/ticker` (sem parâmetro) | `400` | Edge case |

## O passo que prova a economia de cota

Este é o ponto da feature inteira, e vale fazer devagar:

```bash
docker compose exec redis redis-cli FLUSHDB     # cache vazio
docker compose logs -f api                       # deixe rodando noutra janela
```

Agora, no navegador:

1. `http://localhost:8000/ticker/ITSA4` — aquece o cache com **um** ativo.
2. `http://localhost:8000/ticker?ticker=ITSA4&ticker=PETR4` — pede dois.

No log da API, a segunda requisição tem que mostrar **uma única** chamada à
BRAPI, e apenas com `PETR4`. O `ITSA4` saiu do cache e não gastou cota.

Na resposta, `ITSA4` vem com `"cached": true` e `PETR4` com `"cached": false` —
dá para conferir sem olhar o log (SC-006).

## Testes

```bash
docker compose exec api pytest -v
```

E, contra a BRAPI real, para confirmar o teto de ativos por chamada do plano
gratuito — que a documentação não publica:

```bash
docker compose exec api pytest -m contract -v
```

## Problemas comuns

| Sintoma | Causa provável | Solução |
|---|---|---|
| `404` em `/ticker/PETR4` | Imagem antiga | `docker compose up -d --build` |
| Tudo volta com `"cached": false` | Redis não subiu | `docker compose logs redis` |
| `400` num pedido de 3 ativos | `MAX_TICKERS_PER_REQUEST` menor que 3 no `.env` | Ajuste e recrie: `docker compose up -d --force-recreate` |
| `400` num pedido de 4 ativos | Comportamento correto, é o limite | Suba o limite se o seu plano permitir |
