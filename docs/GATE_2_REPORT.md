# Gate 2 — Resultado

## Status

**PASS**

Listagem, recuperação, domínio imutável, validação Lab, latest valid, CLI e integração read-only foram concluídos. Gate 3 não foi iniciado.

## Golden Reference

| Item | Resultado |
|---|---|
| Hash before | `a74672dbde168962bac4d5640d2c0edb2a08fe8e20ad7b01c0062e5a242d15ba` |
| Hash after | `a74672dbde168962bac4d5640d2c0edb2a08fe8e20ad7b01c0062e5a242d15ba` |
| Byte identical | **YES** |
| Golden modificada | **NO** |

## Measurement Model

Classes:

- `MeasurementAngle`: 15, 25, 45, 75, 105;
- `LabValue`: L/a/b reais finitos;
- `MeasurementReference`: ID/GUID/nome/timestamp;
- `Measurement`: identidade, timestamp, serial, temperatura e mapping imutável de Lab;
- `RawBykMeasurement*`: DTOs de infraestrutura que podem refletir ausência.

Validação: exatamente cinco ângulos, 15 valores, nenhum `None`, string inválida, NaN ou infinito. Nenhum zero ou arredondamento é inventado.

## BYK Measurement Commands

| Comando | Resultado |
|---|---|
| `RetrieveMeasurementIdList` / 143 | **PASS**, request real byte-identical |
| `RetrieveMeasurement` / 42 | **PASS**, request ID 3 byte-identical |
| Reuso da mesma conexão | **PASS** |
| Heartbeat durante comandos | **PASS** |

## Real Measurement #3

| Ângulo | L* | a* | b* |
|---:|---:|---:|---:|
| 15° | 77.1218414 | -0.81717968 | 1.26897097 |
| 25° | 57.4835281 | -0.799715519 | 0.563144684 |
| 45° | 30.4952812 | -0.602155924 | -0.0945866108 |
| 75° | 17.905941 | -0.205770135 | -1.66260004 |
| 105° | 13.9409418 | -0.318706036 | -2.96062827 |

15 Lab values: **PASS**. ID 3, GUID, nome, timestamp timezone-aware e serial foram preservados. Valores conferem semanticamente com golden e fixture sem regressão numérica.

## Latest Measurement Strategy

A lista BYK real não traz timestamp. O adapter ordena a listagem por ID ascendente, preservando duplicatas. `get_latest_reference` retorna a referência de maior ID. `get_latest_measurement` percorre IDs distintos em ordem decrescente e retorna o primeiro que parseia e valida completamente; candidatos inválidos são registrados e o método continua. Lista vazia ou nenhum válido gera erro explícito.

Essa política não será usada isoladamente para detectar nova leitura no Gate 3.

## Offline Tests

| Conjunto | Resultado |
|---|---:|
| Previous | 48 passed |
| New | 23 passed |
| Total | 71 passed |
| Failed | 0 |
| Skipped | 0 |
| Deselected `instrument` no default | 4 |

## Integration

| Item | Resultado |
|---|---|
| Gate 1 AUTO | **PASS** |
| Gate 1 MANUAL | **PASS** |
| Gate 2 list/get all | **PASS** |
| IDs 1, 2 e 3 | todos **VALID** |
| Múltiplos retrieves na mesma sessão | **PASS** |
| CLI list/get/latest | **PASS** |
| 20-cycle test a 1,5 s | **20/20 PASS** |

Uma série preliminar com timeout artificial de 0,8 s falhou no terceiro discovery após 2 passes. A série oficial foi reiniciada com 1,5 s e passou 20/20; o default continua 3 s.

## Compatibility

Golden versus new para ID 3: **PASS** em ID, GUID, timestamp, nome e todos os valores Lab. Requests 143/42 e CRC/framing reutilizam fixtures reais do Gate 0.

## Invalid Measurement Tests

| Caso | Resultado |
|---|---|
| Missing angle 105 | **PASS**, rejeitado |
| Missing b* 45 | **PASS**, rejeitado |
| Valor textual inválido | **PASS**, rejeitado |
| `None` | **PASS**, rejeitado |
| NaN | **PASS**, rejeitado |
| Infinity/-Infinity | **PASS**, rejeitado |
| ID inexistente/NOK | **PASS**, erro explícito |
| Lista vazia/latest | **PASS**, erro explícito |

Fixtures sintéticas estão isoladas e rotuladas em `tests/fixtures/byk/synthetic/`; capturas reais do Gate 0 não foram alteradas.

## Technical Debt

1. A listagem real não oferece timestamp; latest usa maior ID como política BYK observada, não regra universal.
2. Discovery com 0,8 s mostrou intermitência; manter default de 3 s e observar instalações.
3. O parser ignora dados espectrais porque estão fora do MVP 1 atual.
4. Respostas reais de erro/incompletas ainda não foram capturadas; testes negativos usam XML sintético rotulado.
5. Gate 3 ainda precisa definir identidade robusta para snapshot e nova leitura.

## Files Created

- `src/mandacor/domain/measurements.py`;
- `src/mandacor/infrastructure/instruments/byk/measurement_dto.py`;
- `src/mandacor/infrastructure/instruments/byk/measurement_parser.py`;
- `src/mandacor/infrastructure/instruments/byk/measurement_mapper.py`;
- `tests/unit/test_measurement_domain.py`;
- `tests/unit/test_byk_measurement_pipeline.py`;
- `tests/unit/test_byk_measurement_adapter.py`;
- `tests/integration/test_byk_measurements_instrument.py`;
- fixtures rotuladas em `tests/fixtures/byk/synthetic/`;
- `docs/ADR_004_MEASUREMENT_DOMAIN_MODEL.md`;
- `docs/GATE_2_REPORT.md`.

## Files Modified

- `src/mandacor/domain/__init__.py`;
- `src/mandacor/ports/instrument.py`;
- `src/mandacor/application/instrument_service.py`;
- `src/mandacor/infrastructure/instruments/byk/constants.py`;
- `src/mandacor/infrastructure/instruments/byk/client.py`;
- `src/mandacor/infrastructure/instruments/byk/adapter.py`;
- `src/mandacor/__main__.py`;
- documentos arquiteturais e estratégia de testes listados no Gate 2.

## Gate 3 — não executado

Após aprovação explícita, o Gate 3 deverá criar snapshot, polling, timeout, cancelamento e `wait_for_new_measurement`, comparando identidade por ID/GUID/timestamp para nunca reutilizar leitura antiga. Nenhum desses componentes foi implementado aqui.

