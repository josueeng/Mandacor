# ADR 012 — Modelo experimental de ajuste

- Status: implementada e validada offline; validação física pendente
- Data: 2026-08-30

## Contexto

Conhecimento qualitativo não demonstra o efeito real de uma intervenção. É necessário registrar o que o operador aplicou e comparar medições explícitas antes/depois sem transformar uma observação isolada em regra ou recomendação quantitativa.

## Decisão

`PendingAdjustment` congela TARGET e BEFORE atuais, contexto, volume `Decimal`, componentes com massa `Decimal`, motivo, UUID próprio e timestamps. O lifecycle distingue PLANNED, APPLIED_WAITING_FOR_AFTER, cancelamento antes da aplicação e abandono explícito após aplicação.

`CompletedAdjustmentTrial` preserva TARGET, BEFORE e AFTER, os dois `ColorComparison`, response AFTER−BEFORE e outcome por cinco ângulos. Improvement usa redução da distância absoluta em L/a/b e redução de ΔE76. Classificações IMPROVED/WORSENED/UNCHANGED são matemáticas, não visuais.

Após uma AFTER válida, a sessão imutável recebe AFTER como sample atual e o trial é anexado ao histórico. Falha antes da conclusão não muda a sessão nem o histórico. Trials multicomponente preservam resposta conjunta e recebem `MIXED_COMPONENTS`; nenhuma atribuição individual é inventada.

## Consequências

O dado permite análise futura, mas não calcula resposta por grama, dose recomendada, score global ou aprovação. Feedback visual e status são opcionais e sempre declarados pelo operador.
