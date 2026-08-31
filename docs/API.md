# API local do MANDACOR

A API é um adaptador FastAPI sobre o core validado nos Gates 0–10. Ela não contém matemática colorimétrica, não escolhe pigmento ou quantidade e não conecta ao BYK durante import ou health check.

## Instalação e inicialização

```bash
virtualenv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m mandacor api serve --host 127.0.0.1 --port 8000
```

Neste ambiente, `virtualenv` é usado porque o Python do sistema não oferece `ensurepip` para `python -m venv`.

O default é `127.0.0.1:8000`. Para testar um cliente na rede local:

```bash
.venv/bin/python -m mandacor api serve --host 0.0.0.0 --port 8000
```

Ao usar `0.0.0.0`, a API fica acessível por outros equipamentos da LAN. Este MVP não implementa autenticação; use apenas em rede confiável. A porta da API é independente das portas BYK TCP 6000 e UDP 6002.

Swagger UI e o schema OpenAPI ficam em `/docs` e `/openapi.json`.

## Regras operacionais

- Existe no máximo um instrumento conectado por processo.
- O ciclo de vida da conexão é centralizado; shutdown desconecta e encerra o heartbeat.
- Sessões, operações e histórico de ajustes em uso pela API ficam em memória e são perdidos ao reiniciar o processo.
- O pending de um ajuste já aplicado continua usando o recovery JSON do Gate 10.
- Nenhum endpoint aceita caminho de filesystem fornecido pelo cliente.
- Todos os valores por ângulo usam uma lista ordenada: 15°, 25°, 45°, 75° e 105°.
- A convenção da comparação é sempre `SAMPLE_MINUS_TARGET`.
- Quantidades e volumes são fatos informados pelo operador e atravessam a fronteira como `Decimal`; a API nunca calcula gramas.

## CORS

CORS é desativado por padrão. Origens devem ser fornecidas explicitamente com uma ou mais opções `--cors-origin`; wildcard `*` é rejeitado.

```bash
.venv/bin/python -m mandacor api serve \
  --cors-origin http://localhost:8081 \
  --cors-origin http://192.168.1.50:8081
```

## Endpoints

| Área | Método e rota |
|---|---|
| Saúde | `GET /health`, `GET /api/v1/health` |
| Instrumento | `GET /api/v1/instrument/status` |
| Instrumento | `POST /api/v1/instrument/discover` |
| Instrumento | `POST /api/v1/instrument/connect` |
| Instrumento | `POST /api/v1/instrument/disconnect` |
| Medições | `GET /api/v1/measurements` |
| Medições | `GET /api/v1/measurements/{measurement_id}` |
| Sessões | `POST /api/v1/sessions` |
| Sessões | `GET /api/v1/sessions/{session_id}` |
| Captura | `POST /api/v1/sessions/{session_id}/target/prepare` |
| Captura | `POST /api/v1/sessions/{session_id}/sample/prepare` |
| Operação | `GET /api/v1/operations/{operation_id}` |
| Operação | `POST /api/v1/operations/{operation_id}/wait` |
| Operação | `POST /api/v1/operations/{operation_id}/cancel` |
| Ciência | `GET /api/v1/sessions/{session_id}/comparison` |
| Ciência | `GET /api/v1/sessions/{session_id}/diagnosis` |
| Ciência | `GET /api/v1/sessions/{session_id}/correction-needs` |
| Pigmentos | `POST /api/v1/sessions/{session_id}/pigment-candidates` |
| Ajustes | `POST /api/v1/sessions/{session_id}/adjustments` |
| Ajustes | `GET /api/v1/sessions/{session_id}/adjustments` |
| Ajustes | `GET /api/v1/adjustments/{adjustment_id}` |
| Ajustes | `GET /api/v1/adjustments/pending` |
| Ajustes | `POST /api/v1/adjustments/{adjustment_id}/confirm-applied` |
| Ajustes | `POST /api/v1/adjustments/{adjustment_id}/after/prepare` |
| Ajustes | `POST /api/v1/adjustments/{adjustment_id}/after/retry` |
| Ajustes | `POST /api/v1/adjustments/{adjustment_id}/abandon` |
| Ajustes | `POST /api/v1/adjustments/{adjustment_id}/feedback` |

## Exemplos essenciais

Health não toca no instrumento:

```bash
curl http://127.0.0.1:8000/health
```

```json
{"status":"ok","service":"mandacor","version":"0.4.0","api_version":"v1","recovery":"OK","recovery_error":null}
```

Conexão automática ou manual:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/instrument/connect \
  -H 'Content-Type: application/json' \
  -d '{"mode":"AUTO"}'

curl -X POST http://127.0.0.1:8000/api/v1/instrument/connect \
  -H 'Content-Type: application/json' \
  -d '{"mode":"MANUAL","host":"192.168.1.13"}'
```

Se a descoberta AUTO retornar mais de um instrumento, a resposta informa os candidatos e não escolhe silenciosamente um deles.

Criar sessão e preparar captura:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/sessions
curl -X POST http://127.0.0.1:8000/api/v1/sessions/SESSION_UUID/target/prepare
curl -X POST http://127.0.0.1:8000/api/v1/operations/OPERATION_UUID/wait \
  -H 'Content-Type: application/json' \
  -d '{"timeout":60,"poll_interval":0.5}'
```

Uma preparação cria o snapshot antes da leitura e devolve um UUID próprio de operação. O cliente pode consultar seu status, chamar `wait` ou solicitar cancelamento cooperativo. Há somente uma captura ativa por sessão. `wait` é uma requisição bloqueante controlada por timeout; uma leitura presente no snapshot nunca é reutilizada.

Contexto para candidatos qualitativos:

```json
{
  "system": "POLYESTER_BASECOAT",
  "finish": "METALLIC"
}
```

A resposta apresenta candidatos, conflitos, riscos, unknowns e justificativas, sempre com `dosage_available: false`.

Criar ajuste com dados decididos pelo operador:

```json
{
  "system": "POLYESTER_BASECOAT",
  "finish": "METALLIC",
  "volume_ml": "250.0",
  "components": [
    {"pigment_code": "CODIGO_INFORMADO", "quantity_g": "0.35"}
  ],
  "operator_reason": "motivo informado pelo operador"
}
```

O fluxo é `PLANNED` → confirmação explícita → `APPLIED_WAITING_FOR_AFTER` → preparação/espera da leitura AFTER → `COMPLETED`. Após timeout de AFTER, o pending permanece aplicado; o cliente deve usar `/after/retry`, sem confirmar nem adicionar novamente a quantidade. O erro possui o código estável `AFTER_MEASUREMENT_TIMEOUT_ADJUSTMENT_ALREADY_APPLIED`.

`GET /api/v1/adjustments/pending` recupera a única intervenção aplicada aguardando AFTER, inclusive depois de reiniciar a API quando o JSON pending existe. `POST /abandon` exige `{"observation":"..."}` e preserva o estado `ABANDONED_AFTER_APPLICATION`. `POST /feedback` aceita `visual_result`, `operator_status` e observações em um trial concluído.

A representação completa de um ajuste concluído contém medições target/before/after, comparações before/target e after/target, resposta observada AFTER−BEFORE, outcomes por ângulo e pior ângulo antes/depois. Todos esses valores são produzidos pelo domínio, não pelo adaptador HTTP ou pelo cliente mobile.

## Erros

Erros controlados seguem um único envelope:

```json
{
  "error": {
    "code": "SESSION_NOT_READY",
    "message": "session is not ready for comparison",
    "details": {},
    "request_id": "7bd4f793-9bb3-4cb0-8c45-f0e412b62cd1"
  }
}
```

O adaptador usa 400 para request semanticamente inválida, 404 para recurso inexistente, 409 para conflito de estado, 422 para validação de schema, 503 para instrumento indisponível/desconectado e 504 para timeout. Stack traces não fazem parte da resposta normal.

Toda resposta inclui `X-Request-ID`; um ID recebido no request é preservado. Erros controlados e inesperados carregam o mesmo ID no envelope. Sessões são persistidas em JSON versionado e o pending continua em arquivo separado, ambos com escrita temporária, `fsync` e substituição atômica. Corrupção não é tratada como estado vazio: o arquivo fica preservado e endpoints dependentes retornam `RECOVERY_FILE_INVALID`.

Diagnóstico local read-only:

```bash
.venv/bin/python -m mandacor doctor
```

O comando não conecta, não captura e não salva configuração; verifica versão, configuração, interfaces, discovery BYK, recovery, diretório de dados e Golden.
