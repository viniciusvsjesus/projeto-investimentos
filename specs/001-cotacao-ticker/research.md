# Pesquisa e decisões técnicas — Spec 001

Cada decisão está no formato ADR resumido: contexto, decisão, alternativas
descartadas e consequências. As decisões tomadas na entrevista estão em
`clarify.md`; aqui ficam as que derivam da investigação técnica.

---

## ADR-001 — Cliente HTTP: `httpx` assíncrono

**Contexto.** A borda é FastAPI assíncrono. Um cliente HTTP bloqueante
(`requests`) dentro de um handler `async` trava o event loop e serializa todas
as requisições concorrentes.

**Decisão.** `httpx.AsyncClient`, instanciado uma vez no ciclo de vida da
aplicação e reaproveitado.

**Alternativas descartadas.**
- `requests` — bloqueante; obrigaria a jogar cada chamada num thread pool.
- `aiohttp` — assíncrono e competente, mas sem cliente de teste equivalente ao
  `respx`, que intercepta `httpx` de forma declarativa e mantém o teste de
  integração legível.

**Consequências.** Reaproveitar a conexão exige gerenciar o ciclo de vida do
cliente no `lifespan` do FastAPI. Timeout obrigatório e explícito — `httpx` tem
padrão de 5s, mas o Artigo VIII exige que seja configurável e consciente.

---

## ADR-002 — Portas como `typing.Protocol`

**Contexto.** O Artigo II exige que `application/` dependa de abstrações, não de
implementações. Python oferece dois caminhos: `abc.ABC` (subclasse nominal) ou
`typing.Protocol` (tipagem estrutural).

**Decisão.** `Protocol` com `@runtime_checkable` apenas onde houver necessidade
real de verificação em tempo de execução.

**Alternativas descartadas.** `abc.ABC` — obriga o adapter a **importar** a
porta e herdar dela. Isso cria acoplamento nominal do adapter para a aplicação,
que funciona, mas inverte menos do que o Protocol: com tipagem estrutural o
adapter não precisa saber que a porta existe, e um dublê de teste vira uma
classe qualquer com os métodos certos, sem herança.

**Consequências.** A conformidade é verificada pelo type checker, não em
runtime. Um adapter que quebra a assinatura da porta só é pego por `mypy` ou
pelos testes — o que torna ambos obrigatórios no CI.

---

## ADR-003 — `Decimal` para valores monetários

**Contexto.** `float` é ponto flutuante binário: `0.1 + 0.2 != 0.3`. Em dado
financeiro isso vira erro de centavo que se acumula.

**Decisão.** `decimal.Decimal` no domínio. A conversão acontece **na borda**: o
mapper converte o número recebido da fonte externa para `Decimal` a partir da
sua representação em texto, e o schema de resposta serializa `Decimal` de volta
para número JSON.

**Detalhe que importa.** A conversão é `Decimal(str(valor))`, nunca
`Decimal(valor)` direto de um `float` — passar um `float` para `Decimal`
preserva o erro binário em vez de eliminá-lo.

**Consequências.** RN-03 satisfeito.

**Detalhe da saída.** O Pydantic serializa `Decimal` como **string** por padrão,
o que produziria `"price": "17.26"` — em desacordo com o `number` prometido em
`contracts/openapi.yaml` e surpreendente para quem consome o JSON. Um
`field_serializer` converte para número no último passo antes de virar bytes.
Todo o trajeto anterior segue em `Decimal`; só a escrita usa o formato que o
JSON tem. Coberto por
`test_valores_monetarios_saem_como_numero_json_e_nao_string`.

---

## ADR-004 — Endpoint da BRAPI e formato de resposta

> **Status: RESOLVIDA.** Ver a seção "RESOLVIDA" ao fim desta ADR — o endpoint
> ativo foi confirmado com payload real em 2026-09-03.

**Contexto.** A documentação pública da BRAPI apresentava **dois** caminhos para
cotação, com formatos de resposta diferentes:

| Geração | Caminho | Formato de `results[0]` |
|---|---|---|
| Legado | `GET /api/quote/{tickers}` | campos no nível raiz do item |
| **v2 (ativa)** | `GET /api/v2/stocks/quote?symbols=...` | `symbol` na raiz, dados de mercado sob `data` |

Não foi possível confirmar por chamada real qual está ativa: o `robots.txt` da
BRAPI bloqueia o acesso automatizado usado nesta pesquisa. Decidir por chute
contraria o Artigo I.

**Decisão.** Três medidas combinadas:

1. O caminho do endpoint é **configuração** (`BRAPI_QUOTE_PATH`), não constante
   no código. Trocar de geração é mudar variável de ambiente, não recompilar.
2. O mapper normaliza o item mesclando os dois níveis, aceitando os dois
   formatos.
3. O **contract test** (`-m contract`, opt-in, com token real) é a prova
   definitiva de qual formato está no ar.

**Alternativa descartada.** Fixar um dos formatos e torcer. Economizaria duas
linhas e criaria uma falha que só aparece em produção.

### RESOLVIDA em 2026-09-03

O autor colou o payload real do painel da BRAPI, com a chamada dele
funcionando. A geração ativa é a **v2**, e o formato é este:

```json
{
  "results": [
    {
      "requestedSymbol": "B3SA3",
      "symbol": "B3SA3",
      "changed": false,
      "data": {
        "shortName": "B3SA3",
        "longName": "B3 SA - Brasil, Bolsa, Balcao",
        "currency": "BRL",
        "regularMarketPrice": 17.26,
        "regularMarketChange": 0.64,
        "regularMarketChangePercent": 3.85,
        "regularMarketTime": "2026-09-03T03:54:59.000Z",
        "marketCap": 80748160464,
        "regularMarketVolume": 41077700,
        "logourl": "https://icons.brapi.dev/icons/B3SA3.svg"
      }
    }
  ],
  "requestedAt": "2026-09-03T12:12:29.182Z",
  "took": 1
}
```

**Duas consequências que a evidência real trouxe, e o palpite não traria:**

1. **`symbol` fica FORA de `data`.** A normalização original —
   `item.get("data", item)` — descartaria o nível externo e perderia o código do
   ativo. O mapper passou a **mesclar** os dois níveis, com `data` vencendo em
   caso de conflito.
2. **`BRAPI_QUOTE_PATH` passa a ter o v2 como padrão**:
   `/api/v2/stocks/quote?symbols={ticker}`. O legado continua suportado e
   testado, para permitir voltar sem recompilar.

O payload acima virou fixture (`brapi_v2_payload_real`) e é exercitado por
testes que rodam offline, sem token — regressão permanente contra mudança
silenciosa de leitura do contrato.

**Registro no Artigo VII.** A configurabilidade do path deixa de ser
especulativa: ela é o que absorveu esta mudança de geração sem tocar no código.

**Autenticação.** Token no header `Authorization: Bearer <token>`, nunca em
query string — a própria documentação da BRAPI alerta que o token em query
vaza para histórico de navegador e log de servidor (Artigo V).

**Sandbox.** `PETR4`, `VALE3`, `MGLU3` e `ITUB4` respondem sem token. Isso
permite validar o fluxo antes de o token estar configurado.

---

## ADR-005 — Cache: chave, TTL e degradação

**Decisão.**
- Chave: `quote:v1:{TICKER}`. O `v1` permite invalidar tudo mudando o prefixo
  quando o formato serializado mudar.
- Valor: JSON do objeto de domínio, serializado no adapter — o domínio não sabe
  o que é JSON.
- TTL: `CACHE_TTL_SECONDS`, padrão `60`. Cotação intradiária envelhece rápido;
  um minuto equilibra frescor e economia de cota.
- Falha do Redis: capturada no adapter, registrada em log no nível `warning` e
  tratada como *cache miss*. Nunca propaga para o caso de uso.

**Consequência.** O caso de uso não tem `try/except` de infraestrutura. Ele
chama a porta; a porta promete não explodir. Isso é o LSP do Artigo III na
prática.

---

## ADR-006 — Duas implementações da porta de cache

**Contexto.** O Artigo VII proíbe abstração com uma implementação só e nenhuma
justificativa.

**Decisão.** `RedisQuoteCache` (produção) e `NullQuoteCache` (sempre *miss*,
nunca grava). O `NullCache` é usado quando `REDIS_URL` está ausente e nos testes
de unidade que não devem depender de cache.

**Consequência.** A porta tem duas implementações reais e um teste que exige o
comportamento correto de ambas. A abstração está justificada, não especulativa.

---

## ADR-007 — Estrutura `src/` com pytest via `pythonpath`

**Contexto.** Sem `src/`, o diretório raiz entra no `sys.path` e o teste passa a
importar o código-fonte por acidente, não pelo caminho instalado.

**Decisão.** Layout `src/investimentos/`, com `pythonpath = ["src"]` no
`pyproject.toml`. No container, `PYTHONPATH=/app/src`.

**Alternativa descartada.** `pip install -e .` — exigiria empacotamento
completo, sem ganho para uma aplicação que roda em container e não é publicada
como biblioteca.

---

## ADR-008 — Imagem Docker: multi-stage e usuário não-root

**Decisão.** `python:3.12-slim`, dois estágios (dependências / runtime),
usuário `appuser` sem privilégio, `HEALTHCHECK` no Dockerfile.

**Justificativa.** O estágio de build isola compiladores e cache do `pip` da
imagem final. Rodar como root dentro do container é risco desnecessário —
qualquer escape de processo herda privilégio.

**Consequência.** `curl` precisa existir na imagem final para o `HEALTHCHECK`,
ou o healthcheck usa Python puro. Escolhido **Python puro**, para não instalar
pacote só para isso — imagem menor e menos superfície.
