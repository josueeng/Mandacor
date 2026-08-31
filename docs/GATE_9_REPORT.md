# GATE 9 — RESULTADO

STATUS: **PASS — STOP antes do Gate 10**

## Golden

- before: `a74672dbde168962bac4d5640d2c0edb2a08fe8e20ad7b01c0062e5a242d15ba`
- after: `a74672dbde168962bac4d5640d2c0edb2a08fe8e20ad7b01c0062e5a242d15ba`
- byte identical: YES

## Tests

- before: 176
- new: 24
- total: 200
- passed: 200
- failed: 0
- instrument deselected offline: 12

## Knowledge Base

- schema version: 1
- revision: `gate-9-initial`
- pigments registered: 31
- profiles validated: 31
- duplicate codes: 0

## Paint Context

- systems: POLYESTER_BASECOAT, PU, UNKNOWN
- finish types: SOLID, METALLIC, PEARL, UNKNOWN
- implicit domain default: NONE

## Provenance

- manufacturer documented: 0
- empirical: 20
- unknown: 11

## Critical Pigments

- AE650: effect opener; mid/flop lightening; flop-opening risk
- BP203: solid lightener; HARD contraindication in metallic/pearl
- BP218: black/darkening with dirtying risks
- BP226: coupled MOVE_GREENER + MOVE_BLUER
- BP267: aluminum, individual effects and particle UNKNOWN
- BP282: fine blue pearl, LIGHTEN + MOVE_BLUER
- BP284: coarse blue pearl, LIGHTEN + MOVE_BLUER
- BP299: polyester additive, ineligible as direct chromatic candidate

## Real Gate 8 Case

- paint context: POLYESTER_BASECOAT / METALLIC
- primary need: 15° / L / LIGHTEN

Candidates by deterministic policy:

1. BP282 — CONDITIONAL; primary match, 7 matches, 3 conflicts, particle/effect/hue risks
2. BP284 — CONDITIONAL; primary match, 7 matches, 3 conflicts, particle/effect/hue risks
3. BP290 — CONDITIONAL; primary match, 7 matches, 3 conflicts, particle/effect/hue risks

Relevant additional candidate:

- BP226 — 9 matches in a*/b*, but conflicts with the 15° yellow-blue need and has no known L* effect

Rejected:

- BP203 — hard contraindication for metallic finish
- BP200 — insufficient directional knowledge
- BP261–BP271 — insufficient individual knowledge
- BP299 — additive, not eligible for direct correction

Warnings:

- LIGHTNESS_CORRECTION_VARIES_WITH_ANGLE
- YELLOW_BLUE_ACTION_VARIES_BY_ANGLE
- NO_SINGLE_SAFE_CANDIDATE
- No dosage calculated

Multiangle conflicts: YES  
Bench test required: YES

## Safety

- white in metallic blocked: PASS
- white in pearl blocked: PASS
- unknown ≠ neutral: PASS
- unregistered effect invented: NO

## Recommendation

- deterministic: YES
- explainable: YES
- grams: NONE
- ML: NONE

## Technical Debt

1. Os 20 perfis conhecidos têm provenance empírica; falta versionar manual/ficha oficial por código.
2. BP261–BP271 exigem experimentos individuais antes de qualquer seleção útil.
3. Ainda não há curva quantidade/volume→efeito nem histórico before/after.

## Files Created

- `src/mandacor/domain/pigments.py`
- `tests/unit/test_pigments.py`
- `docs/PIGMENT_KNOWLEDGE.md`
- `docs/ADR_011_PIGMENT_KNOWLEDGE_BASE.md`
- `docs/GATE_9_REPORT.md`

## Files Modified

- `src/mandacor/__main__.py`
- `docs/COLORIMETRY.md`
- `docs/PRD_MVP1.md`
- `docs/ADR_001_ARCHITECTURE.md`
- `docs/IMPLEMENTATION_PLAN.md`
- `docs/TEST_STRATEGY.md`

## Gate 10 — somente plano

1. Modelar histórico imutável de ajuste vinculado à sessão.
2. Registrar pigmento aplicado e quantidade informada pelo operador, sem recomendá-la.
3. Registrar volume declarado da tinta e suas unidades.
4. Vincular Measurement BEFORE e Measurement AFTER por identidades explícitas.
5. Calcular melhoria/piora por eixo e ângulo sem ocultar conflitos.
6. Produzir dataset versionado e auditável para aprendizado futuro, sem treinar modelo neste estágio.

**Gate 10 não foi executado.**
