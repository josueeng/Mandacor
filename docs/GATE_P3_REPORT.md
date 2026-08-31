# GATE P3 — RESULTADO

STATUS: **PASS — STOP antes do Gate P4 e do Gate 11**

## Scientific State

- Gate 10: **PARTIAL**
- reason: physical trial unavailable
- Gate 11: **NOT STARTED**

Nenhum trial físico foi realizado no P3. Nenhum pending, quantidade, AFTER ou linha de dataset de produção foi criado.

## Product State

- P1: **PASS**
- P2: **PASS**
- P3: **PASS**

## Golden

- before: `a74672dbde168962bac4d5640d2c0edb2a08fe8e20ad7b01c0062e5a242d15ba`
- after: `a74672dbde168962bac4d5640d2c0edb2a08fe8e20ad7b01c0062e5a242d15ba`
- byte identical: **YES**

## Backend

- tests: **278 passed**, 12 deselected
- failed: **0**
- baseline P1/P2: 273 passed
- API extensions: pending global, abandono explícito, feedback; representação completa de target/before/after, response, comparisons, outcomes e worst angles
- restart: pending JSON reidrata ajuste e sessão sem tocar no instrumento
- isolation: TestClient, fake instrument e `tmp_path`; callback de dataset ausente

## Mobile

- tests: **25 passed**, 0 failed, 5 suites
- typecheck: **PASS**, TypeScript strict
- Expo Doctor: **20/20 PASS**
- Expo Android export: **PASS**
- Android: **PASS**, Pixel 7 AVD / Expo Go; Home e rota Adjustment abertas contra FastAPI real

## Adjustment Form

- system: PASS
- finish: PASS
- volume: PASS
- pigment: PASS
- operator quantity: PASS
- multi-component: PASS
- decimal comma: PASS
- presets 450/900/3600 somente preenchem volume: PASS

## Physical Confirmation

- review: PASS
- confirm applied: PASS
- editing blocked after applied: PASS
- warning: PASS — `NÃO ADICIONE O PIGMENTO NOVAMENTE.`
- `PLANNED ≠ APPLIED`: preservado

## AFTER

- prepare: PASS
- snapshot first: PASS — o backend cria o snapshot antes de devolver a operação
- polling: PASS — engine de operação reutilizado do P2
- timeout: PASS — pending permanece aplicado
- retry: PASS
- same adjustment id: PASS
- quantity duplicated: **NO**

`APPLIED + timeout` não significa reaplicar. Retry não chama `confirm-applied` e não envia quantidade.

## Recovery

- app restart: PASS
- pending recovered: PASS
- ambiguous network state: PASS — consulta status e não confirma automaticamente outra vez
- abandon explicit: PASS — registro preservado como `ABANDONED_AFTER_APPLICATION`

## Result

- observed response AFTER−BEFORE: PASS, recebido da API
- before error vs target: PASS, recebido da API
- after error vs target: PASS, recebido da API
- outcomes: PASS, recebido da API
- worst before/after: PASS, recebido da API
- operator feedback: PASS

## History

- list: PASS
- detail: PASS
- sequential chain: PASS no domínio/API; lista cronológica no mobile

## Domain Isolation

- Lab math in mobile: **NO**
- gram prediction: **NO**
- pigment learning: **NO**
- `after.l-before.l`, diferenças de ΔE, `abs(beforeDelta)` ou `quantity/volume` no mobile: **NO**

## Runtime

- FastAPI real: **PASS**
- Expo real: **PASS**
- BYK required: **NO**
- real physical trial: **NOT RUN**

O Pixel 7 abriu o app contra Uvicorn/FastAPI. Uma factory controlada, exclusivamente in-memory, expôs um pending #12/#13 e confirmou visualmente a restauração prioritária na Home e a tela read-only com o aviso de não reaplicação. O botão de leitura AFTER não foi acionado. Após o teste, o processo foi encerrado e `data/` permaneceu sem arquivos.

## Technical Debt

1. Persistir o histórico completo fora da memória para sobreviver ao reinício do processo P1.
2. Definir reconciliação durável para feedback informado depois do append inicial do CSV, sem criar linha duplicada.
3. Repetir o fluxo AFTER em Android com tinta/base física quando ela existir; isso pertence ao fechamento científico do Gate 10, não ao P3.

## Files Created

- `mobile/app/adjustment.tsx`
- `mobile/app/(tabs)/history.tsx`
- `mobile/src/features/adjustments/model.ts`
- `mobile/src/features/adjustments/workflow.ts`
- `mobile/src/__tests__/adjustment-model.test.ts`
- `mobile/src/__tests__/adjustment-workflow.test.ts`
- `docs/ADR_016_MOBILE_ADJUSTMENT_WORKFLOW.md`
- `docs/GATE_P3_REPORT.md`

## Files Modified

- backend: `domain/adjustments.py`, `api/service.py`, `api/schemas.py`, `api/app.py`, `tests/api/test_api.py`
- mobile: API client/types/errors, AppContext, layouts, Home, Results e client tests
- docs: `MOBILE.md`, `API.md`, `IMPLEMENTATION_PLAN.md`, `TEST_STRATEGY.md`, `PRD_MVP1.md`

## Next Gate

Somente plano: **Gate P4 — UX hardening / production readiness**. Possíveis itens: fluxo guiado de bancada, sessão persistente, tratamento de conexão, packaging Android, logs, crash recovery e atualização visual.

**P4 não executado. Gate 11 continua bloqueado até existirem dados físicos reais. PARE.**
