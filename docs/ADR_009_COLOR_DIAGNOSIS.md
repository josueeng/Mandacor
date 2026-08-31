# ADR 009 — Diagnóstico colorimétrico estrutural

- Status: aceita e implementada no Gate 7
- Data: 2026-08-29

## Contexto

`ColorComparison` fornece matemática auditável, mas consumidores precisam de uma representação estruturada do significado dos sinais e do comportamento multiângulo. Essa interpretação não pode recalcular deltas, esconder crossovers com médias nem antecipar recomendação de correção.

## Decisão

`diagnose_comparison` é função pura de domínio. Ela cria `AngleDiagnosis` com direções tipadas, referência ao `AngleComparison` original e eixo dominante pela maior magnitude absoluta; empate exato vira `TIE`. `ColorDiagnosis` conserva identidades, cinco diagnósticos, pior ângulo por ΔE76, ranking estável, summaries de front/mid/flop e padrões globais de sinal.

Front usa 15°/25°, mid preserva 45° diretamente e flop usa 75°/105°. Um resumo regional só adota direção comum se todos os ângulos do grupo concordarem; caso contrário retorna `MIXED`. Igualdade significa delta exatamente zero. Não há epsilon perceptual, média, score ou pass/fail.

Padrões globais distinguem positivo em todos, negativo em todos, igualdade, crossover e mistura com zero. ΔL também recebe tendência monotônica simples na ordem canônica dos ângulos. Ranking empata pelo menor ângulo.

## Alternativas rejeitadas

- Recalcular target/sample: duplica a fonte matemática e pode inverter a convenção.
- Inferir direção por ΔE76: magnitude não contém sinal por eixo.
- Resumir por média: pode ocultar troca de sinal.
- Aplicar limiar de aceitabilidade: não há evidência perceptual aprovada.
- Inferir alumínio, pérola, pigmento ou causa: exige conhecimento de bancada posterior.

## Consequências

Mesma Comparison sempre produz o mesmo Diagnosis sem mutar inputs. O presenter pode traduzir enums, mas o domínio não contém português. Gate futuro poderá validar causas/regras de bancada consumindo esta estrutura, sem alterar os deltas ou os diagnósticos direcionais.
