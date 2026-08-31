# ADR 016 — Workflow de ajuste no mobile

Status: aceito no Gate P3, 2026-08-30.

## Contexto

O ajuste físico precisa distinguir uma intenção (`PLANNED`) de uma intervenção já executada (`APPLIED_WAITING_FOR_AFTER`). Uma resposta de rede ambígua ou timeout da leitura AFTER não pode induzir o operador a adicionar pigmento outra vez. O cliente também não pode duplicar a ciência dos Gates 6–10.

## Decisão

- Sistema, acabamento, volume, pigmentos, massas e motivo são sempre informados pelo operador.
- Presets de 450, 900 e 3600 ml apenas preenchem o campo; não calculam massas.
- Um review local obrigatório precede a criação de `PLANNED` e uma confirmação física forte precede `confirm-applied`.
- Após `APPLIED`, os valores são somente leitura e o aviso `NÃO ADICIONE O PIGMENTO NOVAMENTE.` tem prioridade visual.
- Timeout/offline de `confirm-applied` causa consulta por ID; o cliente nunca repete a confirmação automaticamente.
- Timeout/cancelamento da espera AFTER preserva o mesmo adjustment ID e as mesmas massas. Retry chama somente `/after/retry`.
- O backend é a fonte da verdade. O app persiste apenas IDs de retomada e consulta `/adjustments/pending` no reinício.
- Abandono após aplicação é explícito e preservado como `ABANDONED_AFTER_APPLICATION`.
- Resposta observada, comparações e outcomes são serializados do domínio pela API e apenas apresentados pelo mobile.

## Consequências

O fluxo permanece seguro diante de reinício e ambiguidade de rede. Histórico concluído continua em memória durante o processo P1; o CSV é append-only e feedback posterior não reescreve uma linha já exportada. Persistência durável de todo o histórico e reconciliação do feedback exportado ficam para um gate futuro de production readiness.
