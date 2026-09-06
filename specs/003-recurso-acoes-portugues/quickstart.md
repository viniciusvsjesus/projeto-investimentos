# Quickstart — Spec 003

## Subir

```bash
docker compose up -d --build
```

## Validar

| Passo | URL | Esperado | Critério |
|---|---|---|---|
| 1 | `http://localhost:8000` | Índice em português, anunciando `/acoes` | FR-013 |
| 2 | `http://localhost:8000/acoes/ITSA4` | Um objeto, campos em português | FR-001, FR-004 |
| 3 | `http://localhost:8000/acoes?ticker=ITSA4&ticker=PETR4` | Uma lista de dois | FR-002 |
| 4 | `http://localhost:8000/acoes?ticker=ITSA4` | Lista de **um** elemento | Artigo XI |
| 5 | `http://localhost:8000/ticker/ITSA4` | `404` — rota anterior sumiu | FR-003 |
| 6 | `http://localhost:8000/acoes?ticker=ITSA4&ticker=ZZZZ9` | `situacao` `encontrada` e `naoEncontrada` | FR-005 |
| 7 | `http://localhost:8000/acoes?ticker=PETR` | `400` com corpo RFC 9457 e texto em português | FR-006 |
| 8 | `http://localhost:8000/health` | `{"situacao":"ok","dependencias":{"cache":"ok"}}` | FR-004 |

## O passo que prova a validade decrescente

É o ponto novo desta spec, e precisa de terminal:

```bash
curl -sI "http://localhost:8000/acoes/ITSA4" | grep -i cache-control
sleep 20
curl -sI "http://localhost:8000/acoes/ITSA4" | grep -i cache-control
```

O primeiro traz o TTL cheio (`max-age=60` no padrão). O segundo tem que trazer
**cerca de 40** — o tempo que sobrou. Se vier 60 de novo, o `max-age` está saindo
do TTL configurado em vez do restante, e o SC-004 está sendo violado.

E na lista, com validades diferentes:

```bash
curl -s "http://localhost:8000/acoes/ITSA4" > /dev/null   # aquece um
sleep 20
curl -sI "http://localhost:8000/acoes?ticker=ITSA4&ticker=PETR4" | grep -i cache-control
```

Tem que vir o **menor** dos dois: o ITSA4 com ~40 segundos, não o PETR4 com 60.

## Nenhuma resposta de erro é cacheável

```bash
curl -sI "http://localhost:8000/acoes?ticker=PETR" | grep -i cache-control
```

Tem que dizer `no-store`.

## Testes

```bash
docker compose exec api pytest -v
```

## Problemas comuns

| Sintoma | Causa provável | Solução |
|---|---|---|
| `404` em `/acoes/ITSA4` | Imagem antiga | `docker compose up -d --build` |
| `max-age` sempre igual ao TTL | Validade vindo do configurado, não do Redis | Bug — ver ADR-018 |
| `no-store` sempre | `REDIS_URL` vazia | Confira o `.env` |
| Campo em inglês na resposta | Alias faltando em `schemas.py` | `pytest -k portugues` aponta qual |
