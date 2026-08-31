# Dataset experimental de ajustes

## Proveniência

- Operador: pigment code, quantity_g, volume_ml, motivo, contexto, feedback visual, status e observações.
- Instrumento: Lab de TARGET, BEFORE e AFTER nos cinco ângulos e identidades das Measurements.
- Derivado deterministicamente: comparisons, observed response e outcomes.

Nenhum campo é previsão do MANDACOR.

## Convenções

- error before = BEFORE − TARGET;
- error after = AFTER − TARGET;
- observed response = AFTER − BEFORE;
- improvement por eixo = `abs(error before) − abs(error after)`;
- improvement ΔE = `ΔE before − ΔE after`.

Massa canônica usa gramas em `Decimal`; volume canônico usa ml em `Decimal`. Lab é exportado com representação float completa, sem arredondamento de apresentação. Datas usam ISO-8601 com timezone.

## CSV principal

`adjustments.csv` contém adjustment/session IDs, data, sistema, acabamento, base/cor opcionais, volume, 15 valores TARGET, 15 BEFORE, 15 AFTER, motivo, feedback, identidades e learning eligibility.

Para um componente, `pigmento_adicionado` e `quantidade_g` são preenchidos. Para múltiplos, permanecem vazios para evitar string ambígua; `component_count` e `MIXED_COMPONENTS` identificam o caso.

## CSV de componentes

`adjustment_components.csv` contém uma linha por:

```text
adjustment_id,pigment_code,quantity_g
```

O response de trial multicomponente pertence ao conjunto; não é dividido entre pigmentos.

## Estado do Gate 10

Exportador e schema foram validados com fixtures sintéticas. Nenhum CSV experimental real foi criado, pois não houve intervenção física controlada.
