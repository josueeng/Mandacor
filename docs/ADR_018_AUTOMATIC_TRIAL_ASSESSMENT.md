# ADR 018 — Avaliação automática do resultado do ajuste

- Status: aceita e implementada
- Data: 2026-10-26

## Contexto

O resultado de um ajuste dependia do feedback visual do operador (`visual_result`), que é opcional e frequentemente fica `UNKNOWN`. Para aprender o efeito de cada pigmento, o sistema precisa reconhecer sozinho, pelas leituras, quando um ajuste piorou a cor.

## Decisão

`assess_trial` (`domain/trial_assessment.py`) compara TARGET×BEFORE com TARGET×AFTER e produz um veredito determinístico:

- Por ângulo: ΔE76 melhorou, piorou ou não mudou, com limite de ruído (padrão 0,2 ΔE).
- Por eixo L/a/b (ruído padrão 0,15):
  - `WORSENED_OVERSHOOT`: cruzou o alvo e terminou mais longe (dose excessiva);
  - `WORSENED_WRONG_DIRECTION`: afastou-se do alvo pelo mesmo lado (efeito contrário ao necessário);
  - `IMPROVED` com `crossed_target` quando cruzou o alvo mas terminou mais perto.
- Veredito global: `WORSENED` se o pior ΔE cresceu acima do ruído (o pior ângulo governa a aprovação em bancada); senão `MIXED` se há ângulos melhores e piores; senão `WORSENED`, `IMPROVED` ou `UNCHANGED`.

O veredito é derivado das leituras e nunca é persistido como rótulo separado: pode ser recalculado a partir do dataset (Lab de TARGET/BEFORE/AFTER). O feedback visual continua registrado; quando contradiz o instrumento, `operator_disagrees_with_instrument` sinaliza a divergência.

## Consequências

API, CLI e app mostram "FICOU PIOR", "MELHOROU", "RESULTADO MISTO" ou "SEM MUDANÇA SIGNIFICATIVA" com os eixos responsáveis. Ajustes que pioraram continuam válidos como dado de aprendizado: distinguem dose excessiva de efeito na direção errada.
