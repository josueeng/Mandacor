# ADR 017 — Production readiness local

Status: **ACEITO** em 2026-08-30.

## Contexto

O MVP opera com um app Android e uma FastAPI no PC de bancada. Interrupções de rede, suspensão do app e encerramento do backend não podem transformar estado desconhecido em ação física repetida.

## Decisão

- API, BYK e recuperação são estados distintos. Se a API não responde, o BYK é `UNKNOWN`, nunca presumido desconectado.
- O mobile valida `api_version: v1`, limita todas as chamadas por timeout e mantém somente IDs locais; o backend continua fonte da verdade.
- Sessões e pending adjustment usam JSON versionado e substituição atômica. Arquivo inválido é preservado e exposto como erro de recuperação, sem assumir estado vazio.
- Operações retomadas são reconciliadas por ID. `PREPARED` pode iniciar uma única espera; `WAITING` é apenas consultada. Polling existe somente em foreground e é encerrado em terminal, background e unmount.
- Ações críticas têm guarda contra duplo toque. Confirmação física com resposta ambígua é reconciliada por leitura do ajuste; nunca é reenviada automaticamente.
- Toda resposta HTTP recebe `X-Request-ID`; erros carregam `request_id`. Exceções inesperadas não expõem stack trace.
- `mandacor doctor` é estritamente read-only: valida configuração, rede, discovery, recovery, diretório de dados e Golden sem conectar, capturar ou salvar.

## Consequências

O produto pode abrir e orientar o operador mesmo sem API, sobreviver a reinícios e falhar de modo conservador. O histórico de ajustes concluídos ainda depende do processo/exports existentes; persistência relacional e operação como serviço ficam para um gate futuro.

