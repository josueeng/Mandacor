# GATE 5 — RESULTADO

STATUS: **PASS — STOP antes do Gate 6**

## Golden Reference

- hash before: `a74672dbde168962bac4d5640d2c0edb2a08fe8e20ad7b01c0062e5a242d15ba`
- hash after: `a74672dbde168962bac4d5640d2c0edb2a08fe8e20ad7b01c0062e5a242d15ba`
- byte identical: YES

## Session

- session_id real: `917cf08a-565b-43f9-b424-14a3787d79c7`
- initial state: `WAITING_FOR_TARGET`
- state after target: `TARGET_CAPTURED`
- state while sample request is prepared: `WAITING_FOR_SAMPLE`
- state after sample: `READY_FOR_COMPARISON`
- session_id/created_at preservados: PASS

## Target

- measurement ID: 12
- GUID: `c3734b92-16da-4c33-beca-a7d9fba94686`
- 5 angles: PASS
- 15 Lab: PASS

## Sample

- measurement ID: 13
- GUID: `f90c26ea-2a3a-409b-8986-05d272e9f0c4`
- 5 angles: PASS
- 15 Lab: PASS

## Target Protection

- target before sample capture: 12
- target after sample capture: 12
- unchanged: YES
- expected: YES

## Old Measurement Safety

- target reused as sample: NO
- old measurement returned: NO
- sample ID 13 não existia no snapshot 1–12

## Timeout

- sessão: `3a187add-3f67-4fce-87f3-fb0f8ae4a878`
- target preserved: PASS — ID 12
- sample preserved: PASS — permaneceu `None`
- elapsed: 5,013 s

## Cancellation

- captura inicial preserva target/sample: PASS offline
- recaptura preserva target/sample anterior: PASS offline

## Sample Recapture

- offline: PASS — sample 13 → 14, target inalterado e mesmo UUID
- real: NOT RUN (opcional)

## Stabilization

- same-ID incomplete → valid: PASS
- teste usa `CaptureSampleService` sobre `MeasurementWaitService`; nenhuma lógica de retry foi duplicada.

## Ready State

- `READY_FOR_COMPARISON`: PASS
- invariantes de estados impossíveis: PASS
- comparison criada/calculada: NO

## Tests

- previous: 100
- new: 16
- total offline: 116
- passed: 116
- failed: 0
- instrument deselected no default: 11

## Integration

- sample capture real: PASS — ID 13
- timeout real: PASS
- heartbeat durante captura: RUNNING
- heartbeat após disconnect: STOPPED
- regressão física não interativa: 6 passed, 1 golden protegido/skipped

## Technical Debt

1. A janela finita de stabilization pode expirar antes de consistências muito longas, conforme ID 11 já documentado.
2. Sessão permanece somente em memória; persistência virá em gate futuro.
3. Framing por tag XML e heurísticas Linux de discovery permanecem dívidas anteriores.

## Files Created

- `src/mandacor/application/sample_capture.py`
- `tests/unit/test_sample_capture.py`
- `tests/integration/test_sample_capture_instrument.py`
- `docs/ADR_007_COLOR_SESSION_SAMPLE.md`
- `docs/GATE_5_REPORT.md`

## Files Modified

- `src/mandacor/domain/sessions.py`
- `src/mandacor/application/__init__.py`
- `src/mandacor/__main__.py`
- documentos de arquitetura, produto, plano e testes

## Gate 6

Somente plano: criar um modelo puro de Comparison e, por ângulo, calcular `sample - target` para ΔL, Δa e Δb, além de ΔE76 nos cinco ângulos, seguido de interpretação matemática básica. **Nada disso foi implementado no Gate 5.**
