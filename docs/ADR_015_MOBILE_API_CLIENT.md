# ADR 015 — Mobile como cliente exclusivo da API local

- Status: aceita e implementada no Gate P2
- Data: 2026-08-30

## Contexto

O core científico e a API local P1 já são a fonte validada de instrumento, medição e interpretação. O primeiro app de bancada precisa tornar esse fluxo operacional no Android sem criar uma segunda implementação das regras.

## Decisão

Usar Expo SDK 57, React Native, TypeScript strict e Expo Router. O mobile depende somente de JSON HTTP fornecido pela API P1. `MandacorApiClient` é a única fronteira de `fetch`; telas não conhecem rotas e não executam matemática colorimétrica.

Um contexto React pequeno mantém somente estado de produto necessário: URL, saúde da API, status retornado do instrumento, sessão atual e operação ativa. AsyncStorage persiste URL e IDs, nunca entidades científicas nem segredos. Na retomada, todos os IDs são revalidados no backend.

Captura mantém a transação P1: primeiro `prepare`, depois instrução física, então `wait` acompanhado por polling de 750 ms. Estado de sessão e operação vem do servidor. Double-submit é bloqueado localmente, sem inventar uma state machine concorrente.

Usar quatro abas fixas: Início, Medir, Resultado e Config. Resultados são seções da mesma tela para reduzir toques. Candidatos de pigmento exigem sistema/acabamento informado pelo operador e nunca apresentam dose.

O endereço é configurável por `EXPO_PUBLIC_MANDACOR_API_URL` e pela UI. Android permite cleartext porque a API P1 é HTTP local; esta exceção é explícita no build e documentada. Não há autenticação neste MVP, portanto exposição LAN pressupõe rede confiável.

## Consequências

Backend e mobile evoluem por contrato e enums estáveis. O app funciona offline no sentido de apresentar corretamente a indisponibilidade, mas não simula ciência nem captura sem a API. A persistência de IDs permite retomada enquanto o mesmo processo P1 ainda preserva os repositórios in-memory.

O app não inclui Adjustment Workflow, BEFORE/AFTER, histórico, Gate 11, banco, cloud, ML ou comunicação direta com o BYK.
