# ADR 010 — Necessidade de correção colorimétrica

- Status: aceita e implementada no Gate 8
- Data: 2026-08-29

## Contexto

`ColorComparison` informa quanto a amostra difere do alvo e `ColorDiagnosis` informa como ela está em relação ao alvo. A bancada ainda precisa de uma representação explícita do destino colorimétrico, sem confundi-lo com ação física, pigmento ou quantidade.

## Decisão

`derive_correction_need(diagnosis, comparison)` é função pura. A direção semântica é a inversão do diagnóstico e o vetor numérico é `(-ΔL, -Δa, -Δb)`. O diagnóstico não é recalculado a partir de Measurements; a função valida que Diagnosis e Comparison possuem as mesmas identidades e os mesmos objetos de delta por ângulo.

`AngleCorrectionNeed` preserva as três ações, vetor, eixo dominante e ΔE76. `ColorCorrectionNeed` preserva os cinco ângulos, front 15°/25°, mid 45°, flop 75°/105°, ações globais, uniformidade, flags de variação, worst angle herdado e primary issue. Todos os modelos são congelados e o mapping por ângulo é somente leitura.

Uma região ou eixo global só conserva uma ação se todos os membros concordarem; qualquer conflito vira `MIXED`. Nenhuma média é usada. `NONE` significa somente delta zero exato, sem tolerância perceptual.

Quando o eixo dominante empata, `PrimaryIssue` preserva `TIE` e não inventa uma ação primária. Flags multiângulo descrevem variação, sem inferir alumínio, pérola, limpeza, aplicação ou qualquer causa.

## Separação conceitual

- Comparison: quanto a amostra difere do alvo.
- Diagnosis: em qual direção a amostra está.
- CorrectionNeed: em qual direção a amostra precisa se mover.
- Recommendation: qual ação física ou pigmento usar — ainda inexistente.

## Consequências

O vetor pode ser registrado futuramente em dataset, mas não equivale a gramas: a resposta de pigmento pode ser não linear e depender de base, volume, concentração, efeito e aplicação. O domínio permanece independente de fabricante e pode consumir comparações produzidas por qualquer instrumento compatível.
