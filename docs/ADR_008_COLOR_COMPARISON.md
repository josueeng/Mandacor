# ADR 008 — Comparação colorimétrica pura

- Status: aceita e implementada no Gate 6
- Data: 2026-08-29

## Contexto

A sessão pronta contém target e sample semanticamente explícitos. O sistema precisa calcular diferenças reproduzíveis sem consultar novamente o instrumento, trocar papéis, arredondar o domínio ou introduzir diagnóstico.

## Decisão

A convenção única é `sample - target`. `AngleComparison` é uma dataclass congelada com geometria, ΔL, Δa, Δb e ΔE76. `ColorComparison` é congelada e conserva session UUID, IDs/GUIDs dos papéis e mapping somente leitura, normalizado na ordem 15°, 25°, 45°, 75°, 105°.

`compare_measurements(session_id, target, sample)` pertence ao domínio e executa apenas subtração por ângulo e raiz da soma dos quadrados. Inputs e resultado precisam ser finitos; não há arredondamento interno. `compare_session` pertence à aplicação, exige `READY_FOR_COMPARISON` e delega à função pura.

## Alternativas rejeitadas

- `target - sample`: viola a convenção oficial e inverte direção.
- Um único delta global ou média: perde geometrias independentes.
- Comparar por posição de lista: permite cruzamento de ângulos.
- Consultar latest durante comparação: rompe os papéis congelados da sessão.
- Inserir interpretação/tolerância no motor: mistura matemática com política futura.
- Criar comparison UUID/timestamp: o trio session/target/sample já fornece rastreabilidade suficiente.

## Consequências

A mesma sessão pronta sempre produz o mesmo resultado. Uma sample recapturada exige nova comparação; a anterior não muda. A apresentação pode arredondar, mas o domínio preserva float. Gate 7 poderá consumir os deltas para interpretação, sem alterar esta convenção.
