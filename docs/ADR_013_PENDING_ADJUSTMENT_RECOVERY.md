# ADR 013 — Recovery de ajuste aplicado pendente

- Status: implementada e validada offline
- Data: 2026-08-30

## Contexto

Depois de o operador aplicar fisicamente um pigmento, timeout, desconexão ou restart não podem fazer o sistema solicitar a aplicação novamente.

## Decisão

Ao confirmar APPLIED, o workflow persiste JSON local versionado com adjustment/session IDs, instrumento, TARGET, BEFORE, contexto, volume, componentes, massas e timestamps. `capture-after` recupera o mesmo pending, cria novo snapshot e conserva adjustment ID e quantidades.

O arquivo só é limpo depois que AFTER válida gera trial e os CSVs são persistidos. Cancelamento/timeout mantém o pending. Abandono após aplicação exige confirmação e motivo, grava `ABANDONED_AFTER_APPLICATION` e não apaga silenciosamente o fato.

## Consequências

Recovery não é histórico experimental completo nem banco de dados. Ele protege o estado físico intermediário. No encerramento parcial do Gate 10 nenhum pending existia, pois nenhuma aplicação foi confirmada.
