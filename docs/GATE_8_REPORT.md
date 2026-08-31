# GATE 8 — RESULTADO

STATUS: **PASS — STOP antes do Gate 9**

## Golden

- before: `a74672dbde168962bac4d5640d2c0edb2a08fe8e20ad7b01c0062e5a242d15ba`
- after: `a74672dbde168962bac4d5640d2c0edb2a08fe8e20ad7b01c0062e5a242d15ba`
- byte identical: YES

## Tests

- before: 155
- new: 21
- total: 176
- passed: 176
- failed: 0
- instrument deselected offline: 12

## Model

- `ColorCorrectionNeed`: identidades, cinco ângulos, regiões, global, uniformidade, flags e primary issue
- `AngleCorrectionNeed`: ações L/a/b, vetor inverso, dominante e ΔE76
- immutable: YES
- BYK dependency: NO

## Real Case

Session: `917cf08a-565b-43f9-b424-14a3787d79c7`  
Target: 12  
Sample: 13

| Ângulo | Observed | Need | Correction vector (L, a, b) |
|---:|---|---|---|
| 15° | DARKER / REDDER / BLUER | LIGHTEN / MOVE_GREENER / MOVE_YELLOWER | +2.66778560 / -0.11980534 / +0.07293820 |
| 25° | DARKER / REDDER / YELLOWER | LIGHTEN / MOVE_GREENER / MOVE_BLUER | +1.52559660 / -0.18647313 / -0.29780865 |
| 45° | DARKER / REDDER / YELLOWER | LIGHTEN / MOVE_GREENER / MOVE_BLUER | +0.25867840 / -0.19317865 / -0.43889284 |
| 75° | LIGHTER / REDDER / YELLOWER | DARKEN / MOVE_GREENER / MOVE_BLUER | -0.05139630 / -0.14901161 / -0.38706660 |
| 105° | LIGHTER / REDDER / YELLOWER | DARKEN / MOVE_GREENER / MOVE_BLUER | -0.11994270 / -0.12651086 / -0.35800338 |

## Front

- L: LIGHTEN
- a: MOVE_GREENER
- b: MIXED

## 45°

- L: LIGHTEN
- a: MOVE_GREENER
- b: MOVE_BLUER

## Flop

- L: DARKEN
- a: MOVE_GREENER
- b: MOVE_BLUER

## Global Uniformity

- L: MIXED
- a: UNIFORM — MOVE_GREENER
- b: MIXED

## Primary Issue

- angle: 15°
- group: FRONT
- axis: L
- action: LIGHTEN

## Multiangle Flags

- lightness mismatch: YES
- red-green mismatch: NO
- yellow-blue mismatch: YES

## Forbidden Scope

- pigments: NO
- grams: NO
- aluminum inference: NO
- pearl inference: NO
- clean/dirty inference: NO
- ML: NO

## Mutation Safety

- Comparison unchanged: PASS
- Diagnosis unchanged: PASS
- Session unchanged: PASS
- Measurements unchanged: PASS

## Integration

- real-case deterministic regression: PASS
- new physical measurement: NO
- optional CLI read-only attempt: instrument connection timeout at `192.168.1.13:6000`
- Gate impact: none; this Gate is pure and explicitly requires no real reading

## Technical Debt

1. Equality remains exact zero; any future epsilon must be technical and explicitly justified.
2. CorrectionNeed has no persistence/schema version yet.
3. The CLI demonstration against the stored instrument should be repeated when it is reachable.

## Files Created

- `src/mandacor/domain/correction.py`
- `tests/unit/test_correction.py`
- `docs/ADR_010_CORRECTION_NEED.md`
- `docs/GATE_8_REPORT.md`

## Files Modified

- `src/mandacor/__main__.py`
- `tests/integration/test_comparison_instrument.py`
- `docs/COLORIMETRY.md`
- `docs/PRD_MVP1.md`
- `docs/ADR_001_ARCHITECTURE.md`
- `docs/IMPLEMENTATION_PLAN.md`
- `docs/TEST_STRATEGY.md`

## Gate 9 — somente plano

1. Definir conhecimento estruturado e versionado dos pigmentos, separado do diagnóstico.
2. Modelar sistema/tipo de tinta como contexto explícito de compatibilidade.
3. Registrar efeitos conhecidos por pigmento sobre L/a/b e comportamento multiângulo, sempre com origem e limites.
4. Criar seleção inicial determinística de candidatos e riscos, sem quantidade automática.
5. Validar regras com bancada antes de qualquer recomendação operacional.
6. Não usar machine learning inicialmente; preservar dados para avaliação futura.

**Gate 9 não foi executado.**
