# ADR 006 — Sessão de cor e papel target

- Status: aceita no Gate 4; evoluída pelo ADR 007 no Gate 5
- Data: 2026-08-29

## Contexto

`Measurement` representa dados físicos validados, mas não informa sua função em um trabalho. A captura de alvo precisa provar novidade, preservar identidade do instrumento e permitir recaptura sem perder o alvo anterior em caso de falha.

## Decisão

`ColorSession` é imutável e contém UUID próprio, instante de criação, serial do instrumento, `target: Measurement | None` e estado explícito `WAITING_FOR_TARGET` ou `TARGET_CAPTURED`. Target é um papel: a sessão referencia a mesma `Measurement`, sem duplicar Lab ou criar tipos por ângulo.

`CaptureTargetService` separa preparação e captura. `prepare_target_capture` valida instrumento e cria o snapshot antes de a interface orientar o operador. `capture_target` usa exclusivamente `wait_for_new_measurement`, rejeita defensivamente qualquer identidade já presente no snapshot e retorna uma nova sessão somente após sucesso completo.

Recaptura reutiliza o mesmo fluxo. Como a sessão original é imutável, timeout, cancelamento ou erro deixam o target anterior intacto; uma nova sessão com o mesmo UUID e target substituído só nasce após nova medição válida.

## Alternativas rejeitadas

- Copiar L/a/b para uma classe `TargetMeasurement`: duplica fonte de verdade.
- Usar `get_latest_measurement`: pode associar leitura anterior.
- Apagar target antes da recaptura: perde estado válido se a operação falhar.
- Usar IP como identidade: endereço de infraestrutura pode mudar.
- Introduzir event bus ou máquina de estados completa: complexidade sem uso no Gate 4.

## Consequências

A interface pode exibir semântica “COR ALVO” somente depois do snapshot preparado. Sessão não é persistida neste Gate. No Gate 4 não existiam campo ou comportamento de sample nem comparação; o ADR 007 registra a evolução posterior sem alterar esta decisão histórica.
