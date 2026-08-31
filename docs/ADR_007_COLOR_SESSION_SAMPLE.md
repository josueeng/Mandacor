# ADR 007 — Papel sample na ColorSession

- Status: aceita e implementada no Gate 5
- Data: 2026-08-29

## Contexto

Após a captura do target, a mesma sessão precisa associar outra Measurement nova ao papel sample sem alterar o target. A captura pode falhar, ser cancelada ou encontrar um registro temporariamente incompleto; nesses casos os dados válidos anteriores devem sobreviver.

## Decisão

`ColorSession` continua imutável e ganha `sample: Measurement | None`. Os estados passam a incluir `WAITING_FOR_SAMPLE` e `READY_FOR_COMPARISON`, com invariantes explícitos: espera de target não possui papéis; target capturado possui target e nenhuma sample; espera de sample sempre possui target; prontidão exige os dois papéis.

`CaptureSampleService.prepare_sample_capture` exige target, cria o snapshot antes do prompt e fornece uma `waiting_session` imutável no request. A `base_session` original continua sendo a fonte de rollback. `capture_sample` aceita somente o mesmo estado preparado, chama `wait_for_new_measurement` e produz nova sessão apenas após Measurement completa e posterior ao snapshot.

Recaptura usa o mesmo fluxo. Sucesso substitui somente sample; timeout, cancelamento ou erro preservam target e sample anterior. Session UUID e `created_at` não mudam. Target e sample apontam para Measurements existentes, sem duplicação de Lab.

## Alternativas rejeitadas

- Usar última/penúltima medição: não prova papéis nem novidade.
- Duplicar polling/retry no use case: diverge do hardening do Gate 3.
- Mutar sessão para estado de espera: dificulta rollback em exceções.
- Apagar sample antes de recapturar: perde dado válido em falha.
- Calcular deltas ao entrar em prontidão: pertence ao Gate 6.

## Consequências

`READY_FOR_COMPARISON` significa apenas que target e sample válidos existem. Não contém comparação calculada. Uma recaptura futura do target limpa a sample atual para retornar a um estado coerente de aquisição.
