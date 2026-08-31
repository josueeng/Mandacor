# Relatório do Gate 3 — Snapshot e nova medição

- Data de execução: 2026-08-29
- Instrumento: BYK MicroTriColor, serial 1327634, firmware 1.2.0.24448
- Endpoint observado: 192.168.1.13:6000
- Status: **PASS; hardening adicional concluído no Pre-Gate 4**

## Entrega

Foram implementados `MeasurementIdentity`, `MeasurementSnapshot` e `MeasurementWaitService`, com snapshot imutável, polling síncrono, deadline monotônico, intervalo configurável, cancelamento cooperativo, limite de falhas transitórias, proteção de sessão/instrumento e política determinística para múltiplos candidatos. A CLI recebeu `measurement wait` e usa a expressão neutra `NEW MEASUREMENT DETECTED`.

O domínio permaneceu limpo. Não foram criados alvo, amostra, deltas, comparação, diagnóstico, pigmentos, API, mobile, banco ou machine learning.

## Evidência offline

- `pytest -q`: 88 passed, 6 deselected, 0 failed.
- Baseline anterior preservado: 71/71 testes continuam passando.
- Testes novos do Gate 3: 17.
- Golden reference: `a74672dbde168962bac4d5640d2c0edb2a08fe8e20ad7b01c0062e5a242d15ba`.

Os testes cobrem snapshot, identidade forte/fallback, nenhuma mudança, uma ou várias novas, primeira válida por ID, candidata inválida processada uma vez, estabilização em dois polls, remoção, duplicatas, ID com novo GUID, cancelamento, relógio monotônico, falhas transitórias e mismatch de instrumento/sessão.

## Evidência real

### Sem realizar leitura

Snapshot final: IDs 1–9. Em 5,000 s ocorreram 7 polls. Resultado: `NewMeasurementTimeoutError`; `returned_old_measurement=False`. O ID 9, embora fosse o maior e válido, não foi devolvido.

### Leituras sequenciais

| Ciclo | Snapshot antes | Resultado válido | GUID | Tempo observado |
|---:|---|---:|---|---:|
| 1 | 1–5 | 6 | `2344f4d1-c3e9-4e8e-8bad-7843265ba374` | 105,934 s |
| 2 | 1–6 | 8 | `aa6ea21d-201b-467f-ad0c-ca342886cebc` | 300,156 s |
| 3 | 1–8 | 9 | `7dd99900-9c32-460b-bf02-a5992fa2335d` | 133,046 s |

Todas as retornadas possuem cinco ângulos e 15 valores Lab finitos. Os IDs são distintos e posteriores aos respectivos snapshots. `heartbeat_leak=False` após disconnect.

No ciclo 2, o ID 7 apareceu na listagem ainda incompleto. Ele foi rejeitado, marcado como processado e não causou loop; a leitura seguinte, ID 8, foi validada. Depois da execução, uma integração read-only confirmou que os IDs 1–9 já estavam válidos, evidenciando consistência eventual do armazenamento BYK.

Os tempos incluem coordenação humana por chat e não representam latência do detector. O timeout do teste interativo foi ampliado para 300 s; o default de produção permanece 60 s.

### Regressão de instrumento

`pytest -m 'instrument and not interactive'`: 4 passed, 1 skipped protegido por ambiente e 89 deselected. AUTO, MANUAL, list/retrieve dos IDs 1–9 e o timeout do Gate 3 passaram. A golden foi verificada por hash e pela suíte offline, sem modificação.

## Critérios críticos

- Leitura existente nunca retorna: **PASS**.
- Novo ID é detectado, recuperado e validado: **PASS**.
- Três resultados sequenciais distintos: **PASS** (6, 8 e 9).
- Candidato incompleto não é retornado nem repetido em loop: **PASS** (ID 7).
- Timeout, cancelamento, poll interval e monotonic clock: **PASS**.
- Heartbeat ativo durante wait e encerrado após disconnect: **PASS**.
- Golden reference intacta: **PASS**.

## Dívida técnica e limite do Gate

O framing continua delimitando XML pela tag conhecida, discovery contém heurísticas Linux e não há spectral data; são dívidas já registradas. Uma candidata inválida não é reaberta durante a mesma espera mesmo se ficar válida depois, por decisão de segurança do Gate 3.

## Adendo do Pre-Gate 4

A consulta read-only obrigatória encontrou o ID 7 `COMPLETE`, com cinco ângulos e 15 valores Lab. A condição foi reclassificada de candidata permanentemente inválida para corrida transitória entre listagem e retrieve.

O wait ganhou 5 retries configuráveis a cada 0,5 s, sempre subordinados ao deadline e cancelamento globais. Testes determinísticos provam estabilização do mesmo ID e esgotamento seguido de próximo candidato. Em bancada, uma única leitura ID 10 foi recuperada na segunda tentativa, sem solicitar ID adicional. O ID 11 esgotou a janela curta e ficou completo depois, documentando o limite deliberado da política.
