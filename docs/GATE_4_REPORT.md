# GATE 4 — RESULTADO

STATUS: **PASS — STOP antes do Gate 5**

## Gate 3 Preflight

- ID 7 atual: COMPLETE
- 15 Lab: YES
- Transient race confirmed: YES
- Stabilization retry required: YES
- Stabilization retry implemented: YES — 5 retries, intervalo 0,5 s
- Prova real do mesmo ID: ID 10, válido na segunda tentativa, sem segunda medição

No primeiro ensaio físico, o wait e suas asserções concluíram ID 10 na segunda tentativa; um `NameError` em um `print` posterior do harness causou código de saída não zero e foi corrigido. O reteste com ID 11 esgotou a janela limitada e ficou completo posteriormente. Esse caso não gera loop infinito e permanece dívida operacional documentada, não leitura silenciosamente aceita. A captura real posterior do target ID 12 concluiu com código zero usando o mesmo mecanismo endurecido e uma única leitura.

## Golden Reference

- hash before: `a74672dbde168962bac4d5640d2c0edb2a08fe8e20ad7b01c0062e5a242d15ba`
- hash after: `a74672dbde168962bac4d5640d2c0edb2a08fe8e20ad7b01c0062e5a242d15ba`
- byte identical: YES

## Session

- model: `ColorSession`, frozen dataclass
- session_id real: `933ef803-2db6-49a0-895b-21d21c59388e`
- instrument identity: serial 1327634
- initial state: `WAITING_FOR_TARGET`, target `None`
- captured state: `TARGET_CAPTURED`

## Target Capture

- snapshot: IDs 1–11
- new measurement: ID 12
- target ID: 12
- GUID: `c3734b92-16da-4c33-beca-a7d9fba94686`
- 5 angles: PASS
- 15 Lab: PASS

## Old Measurement Safety

- old measurement returned: NO
- expected: NO

O use case não chama `get_latest_measurement`. Além da garantia do wait, rejeita defensivamente uma Measurement cuja identidade estava no snapshot.

## Timeout

- sessão: `eed3f999-f838-46a2-b562-83a88b98de40`
- target before: `None`
- target after: `None`
- elapsed: 5,000 s
- PASS

## Recapture

- teste unitário: target 4 → target 5, mesmo session UUID
- falha/timeout: target 4 preservado
- integração real: NOT RUN (opcional)
- PASS offline

## Tests

- previous: 88
- hardening new: 2
- Gate 4 new: 10
- total offline: 100
- passed: 100
- failed: 0
- instrument deselected no default: 9

## Integration

- target capture real: PASS — ID 12
- timeout real: PASS
- recapture real: NOT RUN
- heartbeat durante captura: PASS
- heartbeat após disconnect: STOPPED
- regressão real não interativa: 5 passed, 1 golden protegido/skipped

## Technical Debt

1. A consistência eventual pode exceder a janela padrão de 2,5 s, como no ID 11; retries são configuráveis e deliberadamente finitos.
2. O framing XML continua delimitado pela tag empírica conhecida.
3. Discovery mantém dependências/heurísticas Linux já registradas; não há spectral data.

## Files Created

- `src/mandacor/domain/sessions.py`
- `src/mandacor/application/target_capture.py`
- `tests/unit/test_target_capture.py`
- `tests/integration/test_target_capture_instrument.py`
- `docs/ADR_006_COLOR_SESSION_TARGET.md`
- `docs/GATE_4_REPORT.md`

## Files Modified

- `src/mandacor/application/measurement_wait.py`
- `src/mandacor/application/instrument_service.py`
- `src/mandacor/application/__init__.py`
- `src/mandacor/config.py`
- `src/mandacor/infrastructure/config/json_config.py`
- `src/mandacor/__main__.py`
- testes e documentos dos Gates 3/4

## Gate 5

Somente plano: capturar uma nova Measurement como sample na mesma sessão, preservar target, exigir novidade em relação ao snapshot da amostra e tornar a sessão apta à comparação. **Nada disso foi implementado.**
