# Quickstart — Spec 001

Roteiro de validação manual. Se todos os passos passarem, os critérios de aceite
estão satisfeitos na prática, não só no teste.

## Pré-requisitos

- Docker Desktop em execução
- Nada mais. Não é preciso Python instalado na máquina.

## 1. Configurar o ambiente

```bash
cp .env.example .env
```

Abra o `.env` e coloque seu token da BRAPI em `BRAPI_TOKEN`.

Sem token o serviço ainda sobe, mas só os tickers de sandbox (`PETR4`, `VALE3`,
`MGLU3`, `ITUB4`) respondem.

## 2. Subir

```bash
docker compose up -d
```

Confira que os dois serviços estão saudáveis:

```bash
docker compose ps
```

## 3. Validar os critérios de aceite

Tudo pelo navegador. Cada passo é colar uma URL e olhar o JSON.

| Passo | URL ou comando | Esperado | Critério |
|---|---|---|---|
| 1 | `http://localhost:8000` | JSON com `"status": "ok"` e a URL de exemplo | CA-03.1 |
| 2 | `http://localhost:8000/cotacao/PETR4` | `200` com preço, moeda, variação e `quotedAt` | CA-01.1, CA-03.2 |
| 3 | Recarregar a mesma URL na hora | `200` com `"cached": true` | CA-01.5 |
| 4 | `http://localhost:8000/cotacao/petr4` | Mesma resposta de `PETR4` | CA-01.4 |
| 5 | `http://localhost:8000/cotacao/B3SA3` | `200` — código com dígito no prefixo é válido | RN-01 |
| 6 | `http://localhost:8000/cotacao/PETR` | `400` com corpo explicando o formato | CA-01.2 |
| 7 | `http://localhost:8000/cotacao/ZZZZ9` | `404` | CA-01.3 |
| 8 | `http://localhost:8000/health` | `200` com `"status": "ok"` e `"cache": "ok"` | CA-02.1 |
| 9 | `docker compose stop redis`, então repetir o passo 2 | `200` normal, com `"cached": false` | CA-02.2, RF-06 |
| 10 | `/health` com o Redis parado | `"status": "degraded"`, `"cache": "unavailable"` | CA-02.2 |
| 11 | `docker compose start redis` | Volta a `"status": "ok"` | — |

## 4. Rodar a suíte de testes

Dentro do container, sem instalar nada na máquina:

```bash
docker compose exec api pytest -v
```

Testes de unidade e integração rodam offline. O contract test é opt-in:

```bash
docker compose exec api pytest -m contract -v
```

Ele bate na BRAPI de verdade e exige `BRAPI_TOKEN` configurado.

## 5. Conferir que nenhum segredo escapou

```bash
git status --short          # .env NÃO pode aparecer
git check-ignore -v .env    # deve confirmar que está ignorado
```

## 6. Derrubar

```bash
docker compose down          # para os serviços
docker compose down -v       # e apaga o volume do Redis
```

## Problemas comuns

| Sintoma | Causa provável | Solução |
|---|---|---|
| `port is already allocated` na porta 8000 | Outro serviço ocupando a porta | Mudar `API_PORT` no `.env` |
| Toda consulta devolve `502` | Token ausente ou inválido | Conferir `BRAPI_TOKEN` no `.env` e rodar `docker compose up -d --force-recreate api` |
| `"cached"` nunca vira `true` | Redis não subiu | `docker compose logs redis` |
| Alterei o `.env` e nada mudou | O compose lê o `.env` na criação do container | `docker compose up -d --force-recreate` |
| `services.api.env_file must be a string` | Docker Compose anterior à v2.24 | Atualize o Docker Desktop, ou troque o bloco `env_file` por `env_file: [.env]` no `docker-compose.yml` |
| `/cotacao/XXXX9` devolve `404` para um ativo que existe | Ativo fora da cobertura do plano gratuito | Confira o plano no painel da BRAPI |
