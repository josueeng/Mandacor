# GATE 7 — RESULTADO

STATUS: **PASS — STOP antes do Gate 8**

## Golden

- before: `a74672dbde168962bac4d5640d2c0edb2a08fe8e20ad7b01c0062e5a242d15ba`
- after: `a74672dbde168962bac4d5640d2c0edb2a08fe8e20ad7b01c0062e5a242d15ba`
- byte identical: YES

## Tests

- before: 136
- new: 19
- total offline: 155
- passed: 155
- failed: 0
- instrument deselected no default: 12

## Diagnosis Model

- `ColorDiagnosis`: identidades, cinco ângulos, worst/ranking, regiões e padrões
- `AngleDiagnosis`: direções tipadas, dominante e referência ao delta original
- immutable: YES
- BYK dependency: NO

## Real Diagnosis

Session: `917cf08a-565b-43f9-b424-14a3787d79c7`  
Target: 12  
Sample: 13

| Ângulo | ΔL / direção | Δa / direção | Δb / direção | Dominante | ΔE76 |
|---:|---|---|---|:---:|---:|
| 15° | -2.66778560 / DARKER | +0.11980534 / REDDER | -0.07293820 / BLUER | L | 2.67147025 |
| 25° | -1.52559660 / DARKER | +0.18647313 / REDDER | +0.29780865 / YELLOWER | L | 1.56553735 |
| 45° | -0.25867840 / DARKER | +0.19317865 / REDDER | +0.43889284 / YELLOWER | B | 0.54484808 |
| 75° | +0.05139630 / LIGHTER | +0.14901161 / REDDER | +0.38706660 / YELLOWER | B | 0.41793133 |
| 105° | +0.11994270 / LIGHTER | +0.12651086 / REDDER | +0.35800338 / YELLOWER | B | 0.39819300 |

## Worst Angle

- 15° por maior ΔE76

## Ranking

1. 15°
2. 25°
3. 45°
4. 75°
5. 105°

## Front Summary

- Lightness: DARKER
- Red/Green: REDDER
- Yellow/Blue: MIXED

## Mid Summary

- 45°: DARKER / REDDER / YELLOWER; dominante B

## Flop Summary

- Lightness: LIGHTER
- Red/Green: REDDER
- Yellow/Blue: YELLOWER

## Multiangle Patterns

- L: SIGN_CROSSOVER; ΔL monotonicamente crescente com o ângulo
- a: POSITIVE_ACROSS_ALL
- b: SIGN_CROSSOVER

## Mutation Safety

- comparison unchanged: PASS
- session unchanged: PASS
- measurements unchanged: PASS

## Integration

- CLI diagnosis read-only: PASS
- regression instrument: 7 passed, 1 golden protegido/skipped
- new physical measurement: NO
- heartbeat stopped: YES

## Forbidden Scope

- pigment recommendation: NO
- gram adjustment: NO
- ML: NO
- tolerance/pass-fail: NO
- physical cause inference: NO

## Technical Debt

1. Igualdade é zero exato; qualquer epsilon futura precisará ser justificada como precisão numérica, não tolerância perceptual.
2. Padrões descrevem sinais/tendência, não causas físicas.
3. Diagnosis ainda não possui persistência ou versão de schema.

## Files Created

- `src/mandacor/domain/diagnosis.py`
- `tests/unit/test_diagnosis.py`
- `docs/ADR_009_COLOR_DIAGNOSIS.md`
- `docs/GATE_7_REPORT.md`

## Files Modified

- `src/mandacor/__main__.py`
- `tests/integration/test_comparison_instrument.py`
- documentação de colorimetria, produto, arquitetura, plano e testes

## Gate 8

Somente plano: validar e acrescentar conhecimento de bancada sobre comportamento de efeito e possíveis causas, preservando separação entre diagnóstico e recomendação. **Nada disso foi implementado no Gate 7.**
