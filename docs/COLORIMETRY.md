# Colorimetria do MVP 1

## Dados preservados

Cada `Measurement` guarda individualmente L*, a* e b* nos ângulos 15°, 25°, 45°, 75° e 105°. São 15 valores numéricos finitos obrigatórios. Ausência, `NaN`, infinito, texto ou ângulo inesperado invalida a leitura para comparação; valores nunca são preenchidos com zero.

L* representa luminosidade; a* posiciona a cor no eixo verde–vermelho; b* no eixo azul–amarelo. O MVP não agrega nem substitui os dados brutos por front/face/flop. Futuramente, 15°+25° podem informar front, 45° face e 75°+105° flop.

## Convenção de comparação do MANDACOR — implementada no Gate 6

Para cada ângulo, sempre `AMOSTRA - ALVO`:

```text
ΔL = L_amostra - L_alvo
Δa = a_amostra - a_alvo
Δb = b_amostra - b_alvo
ΔE76 = sqrt(ΔL² + Δa² + Δb²)
```

ΔE76 é uma distância complementar, sem direção; não substitui os três deltas.

Onde `s` é sample/amostra e `t` é target/alvo. A subtração nunca é invertida e cada geometria é comparada somente consigo mesma: 15° com 15°, 25° com 25°, 45° com 45°, 75° com 75° e 105° com 105°. O domínio preserva `float` sem arredondamento; arredondamento é exclusivamente visual.

## Significado matemático dos sinais

- L* maior aponta para mais claro e L* menor para mais escuro. ΔL positivo significa amostra relativamente mais clara; ΔL negativo, relativamente mais escura.
- a* positivo aponta para vermelho e a* negativo para verde. Δa positivo significa amostra relativamente mais vermelha; Δa negativo, relativamente mais verde.
- b* positivo aponta para amarelo e b* negativo para azul. Δb positivo significa amostra relativamente mais amarela; Δb negativo, relativamente mais azul.

O sinal é relativo. Se target a* = -4 e sample a* = -2, então Δa = +2 embora ambos estejam no lado verde. Analogamente, target b* = -5 e sample b* = -2 produz Δb = +3 embora ambos estejam no lado azul.

ΔE76 é sempre não negativo e representa apenas magnitude naquele ângulo. Sozinho não informa nenhuma direção e não substitui ΔL, Δa ou Δb.

## Interpretação determinística futura — não implementada no Gate 6

Com tolerância não negativa `t` por eixo:

| Eixo | delta > t | delta < -t | caso contrário |
|---|---|---|---|
| L* | amostra mais clara | amostra mais escura | luminosidade próxima |
| a* | amostra mais vermelha | amostra mais verde | eixo verde–vermelho próximo |
| b* | amostra mais amarela | amostra mais azul | eixo azul–amarelo próximo |

Os limites são inclusivos na faixa neutra: `-t <= delta <= t`. Tolerâncias pertencem à configuração/política da aplicação, não ao instrumento.

Esta seção registra intenção futura do MVP. O Gate 6 não cria tolerâncias, classificação, aprovação/reprovação, diagnóstico ou recomendação.

## Modelo conceitual

- `LabValue(L, a, b)` imutável.
- `Measurement(..., angles: Mapping[Angle, LabValue])` imutável e validada.
- `AngleComparison(delta_l, delta_a, delta_b, delta_e76)` imutável.
- `Comparison(target, sample, angles)` associa explicitamente as duas leituras.

Metadados preservam ID, GUID, timestamp, fonte, ID/serial do instrumento e temperatura quando disponíveis. Serialização externa inclui `schema_version`.

## Modelo implementado no Gate 2

- `MeasurementAngle` é um `IntEnum` restrito a 15, 25, 45, 75 e 105.
- `LabValue` é uma dataclass congelada e aceita somente números reais finitos.
- `Measurement` é congelada e expõe `angles` por mapping somente leitura.
- O timestamp ISO real é convertido por `datetime.fromisoformat`; `+00:00` permanece timezone-aware. O texto original também é preservado; timezone nunca é inventado.
- O pipeline bruto pode representar ausência, mas o mapper nunca cria `Measurement` com `None` em Lab.

O Gate 2 não implementa interpretação, agregação front/face/flop, deltas ou ΔE.

## Modelo implementado no Gate 6

- `AngleComparison` conserva ângulo, ΔL, Δa, Δb e ΔE76 como valores finitos e sem arredondamento.
- `ColorComparison` conserva session UUID, IDs/GUIDs de target/sample e mapping imutável em ordem 15°, 25°, 45°, 75°, 105°.
- `compare_measurements` é matemática pura `sample - target`, sem instrumento, tempo, arquivo ou aleatoriedade.
- `compare_session` exige `READY_FOR_COMPARISON` e não modifica a sessão nem suas Measurements.

## Diagnóstico estrutural implementado no Gate 7

`ColorDiagnosis` interpreta somente os sinais já presentes em `ColorComparison`. Zero significa igualdade matemática exata, não tolerância visual. Cada ângulo preserva suas direções L*/a*/b*, ΔE76 e eixo dominante por maior magnitude absoluta; empate produz `TIE`.

O agrupamento operacional é:

- front: 15° e 25°;
- mid/intermediate: 45°;
- flop/lateral: 75° e 105°.

Os cinco ângulos permanecem individualmente disponíveis. Resumos de dois ângulos retornam `MIXED` quando os sinais divergem; nenhuma média pode esconder crossover. `worst_angle` usa maior ΔE76, com desempate pela ordem 15°, 25°, 45°, 75°, 105°.

Padrões globais descrevem sinais positivos/negativos em todos os ângulos, igualdade, crossover ou presença mista com zero. A tendência de ΔL pode ser crescente, decrescente, constante ou não monotônica. Esses resultados não atribuem causa a pigmento, alumínio, pérola, aplicação ou espessura e não recomendam correção.

## Necessidade de correção implementada no Gate 8

`ColorCorrectionNeed` responde para onde a amostra precisa se mover no espaço Lab. Como a comparação é `SAMPLE - TARGET`, o vetor necessário é exatamente o oposto: `(-ΔL, -Δa, -Δb)`. Esse vetor preserva magnitude matemática e não representa gramas nem presume resposta linear de pigmento.

As ações são derivadas das direções do diagnóstico: DARKER→LIGHTEN, LIGHTER→DARKEN, REDDER→MOVE_GREENER, GREENER→MOVE_REDDER, YELLOWER→MOVE_BLUER e BLUER→MOVE_YELLOWER. `NONE` existe apenas para zero matemático.

Front usa 15°/25°, mid preserva 45° e flop usa 75°/105°. Divergência vira `MIXED`; uma ação global só existe quando os cinco ângulos concordam. Flags multiângulo são descritivas e não atribuem causa física. Em particular, MOVE_BLUER não significa adicionar pigmento azul, e mismatch de luminosidade não significa problema de alumínio.

## Seleção qualitativa implementada no Gate 9

O efeito conhecido de um pigmento é comparado às necessidades de cada eixo em cada um dos cinco ângulos. Match, conflito e efeito desconhecido permanecem separados. Perfil específico tem prioridade sobre regras cromáticas genéricas; nomes e códigos próximos nunca geram efeito por inferência.

O ranking é lexicográfico: ausência de conflito no primary issue, match no primary issue, quantidade de matches ângulo-eixo, menos conflitos, menos unknowns e código como desempate. Não existe score, ΔE hipotético ou modelo de dose. Contraindicações de contexto são aplicadas antes do ranking; BP203 é bloqueado em metálico e pérola.

A recomendação significa apenas “candidato qualitativamente compatível sob o contexto informado”. Todo ajuste físico exige teste em chapinha e nova medição. Nenhuma quantidade é calculada.

## Modelo experimental implementado no Gate 10

O histórico distingue rigorosamente três vetores por ângulo:

- error before: `BEFORE - TARGET`, calculado pelo `ColorComparison` existente;
- error after: `AFTER - TARGET`, também calculado por `ColorComparison`;
- observed response: `AFTER - BEFORE`, que descreve somente o ocorrido naquele trial.

Improvement por eixo é `abs(error_before) - abs(error_after)`; improvement de ΔE76 é `ΔE_before - ΔE_after`. Valores positivos aproximam matematicamente, negativos afastam e zero é igualdade exata. Crossover pode melhorar e overshoot pode piorar. Não há média global, tolerância perceptual nem efeito por grama.

O Gate 10 terminou `PARTIAL`: toda a matemática e o workflow foram validados offline, mas nenhum vetor experimental real foi produzido porque a tinta física correspondente ao BEFORE #13 não estava disponível.
