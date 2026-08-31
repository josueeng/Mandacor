# Estratégia de testes

## Princípios

Testes offline são o default; acesso ao instrumento é explícito. Frames e XMLs reais, sanitizados apenas quando necessário, guardam hash, firmware/data/origem e não são "corrigidos" manualmente. A golden reference recebe caracterização antes da extração.

## Unitários

- Validação de cinco ângulos, valores ausentes, tipos inválidos, NaN e infinito.
- ΔL: alvo 50, amostra 52 → +2.
- Δa: alvo 1, amostra -1 → -2 → mais verde.
- Δb: alvo 2, amostra -1 → -3 → mais azul.
- ΔE76 com vetores conhecidos, zero e sinais mistos.
- Limites `-t`, `+t`, imediatamente dentro e fora da tolerância.
- Estado da sessão: target antes de sample e comparação somente com ambos.
- Serialização/releitura schema v1 e gravação atômica do repositório.

## Parser e protocolo offline

- `measurement_*.xml`: sucesso real, resultado NOK, registro sem `MeasureValue`, LAB incompleto e temperatura inválida se observados.
- `frame_*.bin`: ACK e respostas reais com header/payload/CRC preservados.
- Vetores fixos de `BYKQUERY`, headers dos IDs 4/42/143 e CRC XMODEM conhecido.
- Extração de XML, validação de magic/CRC e erros truncados.
- Stream simulado com fragmentação em cada fronteira e, se observado, frames coalescidos.
- Mapeamento XML → `Measurement` sem rede.

Fixtures sintéticas complementares serão rotuladas como sintéticas e não substituirão capturas reais.

## Testes de adaptadores/aplicação

Usar doubles de socket, relógio e `InstrumentAdapter` para testar descoberta, retries, heartbeat, limpeza, snapshot, polling, cancelamento e timeout de forma determinística. Verificar especialmente que um snapshot imutável seguido da mesma lista nunca produz medição.

## Integração com instrumento

Marcador `pytest -m instrument`; desabilitado no conjunto padrão e protegido por configuração explícita. Cobrir apenas operações de leitura:

1. discover/heartbeat;
2. connect/get_info/disconnect;
3. listagem;
4. recuperação de uma medição conhecida;
5. espera de nova medição assistida pelo operador.

Registrar modelo, serial mascarado quando necessário, firmware, rede, timings e resultado. Gate 1 exige 20 ciclos ou substituto aprovado.

## End-to-end em bancada

Roteiro manual assistido e repetível:

1. iniciar `mandacor compare` sem criar medição;
2. confirmar que nenhuma leitura antiga é aceita;
3. medir alvo e conferir identidade/15 valores;
4. medir amostra e conferir identidade distinta/15 valores;
5. conferir deltas por cálculo independente;
6. conferir mensagens direcionais;
7. conferir JSON persistido e releitura;
8. repetir a sessão e testar timeout/Ctrl+C.

## Execução e gates de qualidade

- `pytest`: todos os testes offline.
- `pytest -m instrument`: somente bancada autorizada.
- Formatter/linter/type checker serão definidos no Gate 0 sem introduzir dependências de runtime desnecessárias.
- Cada correção de bug adiciona teste de regressão.
- Nenhum gate avança com testes offline falhando ou sem evidência de seu critério de bancada.

## Resultado do Gate 0

- **CONFIRMADO POR TESTE:** após a captura, `pytest -q` executou 22 testes com sucesso, sem falhas/skips, e deselecionou 1 teste marcado `instrument`.
- **CONFIRMADO POR TESTE:** original/golden têm o hash aprovado e bytes idênticos; query, headers, CRC, ACK, fragmentação, risco de coalescência e parser atual foram caracterizados offline.
- **CONFIRMADO POR TESTE:** todos os dados não reais usados estão marcados `SYNTHETIC_TEST_DATA`.
- **CONFIRMADO EM BANCADA:** a primeira execução ocorreu com o instrumento desligado; o reteste read-only passou discovery, heartbeat, TCP e os três comandos.
- **CONFIRMADO POR FIXTURE:** `BYKINSTRUMENT`, streams TCP, XML de instrumento/lista/medição, ACK, header, payload, CRC e valores Lab reais foram preservados com SHA-256.

## Resultado do Gate 1

- Suíte offline: 48 passed, 0 failed, 3 testes de instrumento deselecionados.
- Gate 0 preservado: 22 testes continuam passando.
- Gate 1 offline: 26 testes novos para IP/config, JSON, broadcast `/24`/`/23`/`/16`, BYKQUERY, reconhecimento, deduplicação, CRC/framing real, buffer coalescido, parser, heartbeat, estados, fallback, timeout e recusa de conexão.
- Integração modular marcada `instrument`: 2 passed (AUTO e MANUAL).
- Ensaio adicional: 20 ciclos AUTO consecutivos passaram, verificando modelo/firmware e ausência de heartbeat ao final.
- A golden manteve seu hash e não foi usada como código de produção.

## Resultado do Gate 2

- Suíte offline: 71 passed, 0 failed, 4 testes `instrument` deselecionados.
- Baseline anterior: 48 testes continuam verdes.
- Gate 2: 23 testes novos cobrem domínio imutável, 5 ângulos/15 valores, fixture real, golden compatibility, requests, namespace, duplicatas, ordenação, latest valid, lista vazia, ID inexistente e erros sintéticos.
- Inválidos: ângulo ausente, coordenada ausente, string inválida, NaN, infinito e `None` são rejeitados sem preenchimento.
- Integração: 2 testes Gate 1 + 1 teste Gate 2 passaram; IDs 1, 2 e 3 são válidos.
- Robustez: 20/20 ciclos com listagem e retrieve #3 passaram a 1,5 s; 0,8 s apresentou uma falha de discovery no terceiro ciclo e foi registrado como timeout excessivamente agressivo.

## Resultado do Gate 3

- Suíte offline: 88 passed, 0 failed, 6 testes de instrumento deselecionados; os 71 testes anteriores continuam verdes.
- Gate 3: 17 testes determinísticos cobrem snapshot vazio/existente, identidade ID+GUID+serial, timeout sem leitura velha, estabilização, uma/múltiplas novas, inválida seguida de válida, remoção, duplicatas, GUID reutilizado, cancelamento, deadline monotônico, falhas transitórias e troca de instrumento/sessão.
- Teste real sem medir: snapshot IDs 1–9, 7 polls em 5,000 s, `NewMeasurementTimeoutError`, nenhuma leitura antiga retornada.
- Integração não interativa: 4 passed e 1 golden protegido/skipped; AUTO, MANUAL, list/retrieve de IDs 1–9 e timeout passaram.
- Teste real interativo: três ciclos de snapshot → leitura → detecção retornaram IDs 6, 8 e 9, todos com cinco ângulos e 15 valores Lab; `heartbeat_leak=False` ao final.
- Evidência de robustez: ID 7 foi listado enquanto ainda inválido, processado uma vez e não retornado; o serviço prosseguiu e aceitou o ID 8 válido.

## Pre-Gate 4 — hardening do Gate 3

- Consulta read-only posterior confirmou ID 7 completo, com cinco ângulos e 15 valores Lab: corrida transitória confirmada.
- Dois testes determinísticos novos cobrem `INCOMPLETE → INCOMPLETE → VALID` no mesmo ID e esgotamento limitado seguido de outro ID válido.
- Retry configurável: 5 retries, intervalo 0,5 s; timeout e cancelamento globais permanecem soberanos.
- Bancada: ID 10 exigiu duas tentativas de retrieve e foi retornado completo sem segunda medição física. ID 11 esgotou a janela, não causou loop e ficou completo posteriormente, confirmando que a consistência eventual pode exceder o limite deliberado.

## Resultado do Gate 4

- Suíte offline: 100 passed, 0 failed, 9 testes de instrumento deselecionados.
- Dez testes novos cobrem sessão inicial, UUID/estado, captura sem latest, defesa contra leitura velha, timeout/cancelamento, recaptura, falha de recaptura, imutabilidade, instrumento e request de outra sessão.
- Timeout real: snapshot IDs 1–11, 5,000 s, target `None` antes/depois e nenhuma leitura antiga retornada.
- Captura real: sessão `933ef803-2db6-49a0-895b-21d21c59388e`, target ID 12, GUID `c3734b92-16da-4c33-beca-a7d9fba94686`, cinco ângulos e 15 valores Lab.
- Recaptura real é opcional e não foi executada; sucesso e preservação em falha estão cobertos deterministicamente.
- Regressão física não interativa final: 5 passed, 1 golden protegido/skipped; AUTO, MANUAL, IDs 1–12, timeout de medição e timeout de target passaram.

## Resultado do Gate 5

- Baseline preservado: 100 testes anteriores continuam verdes.
- Gate 5 adicionou 16 testes offline: pré-condição de target, estado de espera, atribuição/proteção, identidade/created_at, rejeição de leitura velha, timeout/cancelamento, recaptura, invariantes impossíveis, request obsoleto e corrida `INCOMPLETE → VALID` no mesmo ID por meio do wait real.
- Suíte offline: 116 passed, 0 failed, 11 testes de instrumento deselecionados.
- Timeout real: target ID 12 inalterado, sample `None`, nenhuma leitura antiga devolvida, 5,013 s.
- Captura real: sessão `917cf08a-565b-43f9-b424-14a3787d79c7`, target 12 → 12, sample ID 13/GUID `f90c26ea-2a3a-409b-8986-05d272e9f0c4`, cinco ângulos, 15 Lab e estado `READY_FOR_COMPARISON`.
- Recaptura real não foi executada; substituição exclusiva da sample e rollback em falha estão cobertos deterministicamente.
- Regressão física não interativa final: 6 passed, 1 golden protegido/skipped; IDs 1–13 e timeouts de medição, target e sample passaram.

## Resultado do Gate 6

- Baseline preservado: 116 testes anteriores continuam verdes.
- Gate 6 adicionou 20 testes offline para zero, convenção sample−target, sinais positivos/negativos, eixos negativos relativos, ΔE 3–4–5 e 1–2–2, cinco ângulos independentes, ordem, precisão, decimal não trivial, identidades, imutabilidade, dados incompletos/não finitos e estados da sessão.
- Suíte offline: 136 passed, 0 failed, 12 testes de instrumento deselecionados.
- Integração read-only: IDs documentados 12/13 recuperados, comparação dos cinco ângulos passou e heartbeat encerrou.
- Verificação independente 15°: manual e engine coincidiram em ΔL `-2.667785600000002`, Δa `0.11980533589999999`, Δb `-0.07293820360000002`, ΔE76 `2.6714702520563236`.
- Regressão física não interativa final: 7 passed, 1 golden protegido/skipped; comparação e timeouts anteriores passaram.

## Resultado do Gate 7

- Baseline preservado: 136 testes anteriores continuam verdes.
- Gate 7 adicionou 19 testes offline para seis direções + zero, eixos absolutos negativos, dominante L/a/b/tie, ranking e desempate, cinco ângulos, front/mid/flop, MIXED sem média, padrões globais, tendência de ΔL, independência de ΔE para direção, regressão real e imutabilidade/determinismo.
- Suíte offline: 155 passed, 0 failed, 12 testes de instrumento deselecionados.
- CLI read-only com IDs 12/13 produziu o diagnóstico esperado sem nova medição.
- Integração real estendida preserva sessão/Measurements e confirma worst 15°, ranking 15→105°, L*/b* crossover e a* positivo em todos os ângulos.
- Regressão física não interativa final: 7 passed, 1 golden protegido/skipped; diagnóstico e todos os fluxos anteriores permaneceram verdes.

## Resultado do Gate 8

- Baseline preservado: 155 testes anteriores continuam verdes.
- Gate 8 adicionou 21 testes offline para inversões L/a/b, zero exato, vetor inverso, cinco ângulos, front/mid/flop, conflitos, uniformidade dos cinco ângulos, flags por eixo, caso real, prioridade, determinismo, imutabilidade e desacoplamento.
- Suíte offline: 176 passed, 0 failed, 12 testes de instrumento deselecionados.
- O caso real target 12/sample 13 é fixture matemática do teste, com todos os deltas dos Gates 6/7 preservados.
- Uma tentativa opcional da CLI read-only em `192.168.1.13:6000` terminou em timeout de conexão. Gate 8 não requer nova captura nem instrumento disponível; não houve alteração de medição.

## Resultado do Gate 9

- Baseline preservado: 176 testes anteriores continuam verdes.
- Gate 9 adicionou 24 testes offline para unicidade/validação, provenance, unknown≠neutral, regras cromáticas gerais isoladas, pigmentos críticos, alumínios desconhecidos, contexto, contraindicações, matches, conflitos, primary issue, ranking e imutabilidade.
- Suíte offline: 200 passed, 0 failed, 12 testes de instrumento deselecionados.
- Fixtures críticas cobrem pigmento que clareia front e conflita no flop, verde uniforme nos cinco ângulos e efeito acoplado que ajuda b* enquanto piora a*.
- Caso real do Gate 8 em contexto metálico retorna candidatos condicionais, BP203 contraindicado e `NO_SINGLE_SAFE_CANDIDATE`.
- Nenhum teste ou fluxo do Gate 9 exige instrumento ou nova leitura.

## Resultado parcial do Gate 10

- Baseline preservado: 200 testes anteriores continuam verdes.
- Gate 10 adicionou 52 testes offline; suíte total: 252 passed, 0 failed, 12 testes de instrumento deselecionados.
- Domínio: response AFTER−BEFORE, cinco ângulos, improvement por distância absoluta/ΔE, crossover, overshoot, Decimal, componentes, lifecycle, imutabilidade e histórico sequencial.
- Workflow: pending persistido após APPLIED, timeout sem mutação/duplicação, retry com mesmo UUID, leitura antiga recusada, atualização atômica da sample e limpeza somente após export durável.
- Dataset: headers determinísticos, precisão Lab, timestamps ISO, single/mixed, componentes normalizados, feedback opcional e append sem sobrescrever histórico.
- Trial físico: **NÃO EXECUTADO** por ausência da tinta/base física correspondente ao BEFORE #13. Por critério do Gate, status final `PARTIAL`.
- Evidência negativa: nenhum pending, CSV experimental, quantidade ou AFTER fictício foi criado.

## Resultado do Gate P1

- Baseline preservado: 252 testes anteriores continuam verdes.
- Gate P1 adicionou 21 testes offline com factory e fake instrument; suíte total: 273 passed, 0 failed, 12 testes de instrumento deselecionados.
- Cobertura: health sem conexão, discovery/conexão/desconexão, múltiplos candidatos, list/retrieve, sessões, snapshots, conflito/cancelamento/timeout, target/sample, comparação, diagnóstico, correção, pigmentos, ajustes, recovery sem duplicar gramas, error envelope, OpenAPI e CORS.
- Auditoria de isolamento: nenhum import FastAPI/Starlette/Pydantic/HTTP foi introduzido em domain/application e nenhuma fórmula ou regra BP203 foi colocada nas routes.
- Smoke API BYK read-only tentado: status/disconnect passaram; AUTO connect terminou em timeout controlado, portanto list/retrieve não foram executados. Nenhuma leitura física foi criada e o resultado opcional não bloqueia P1.
- Golden preservada com SHA-256 `a74672dbde168962bac4d5640d2c0edb2a08fe8e20ad7b01c0062e5a242d15ba`.

## Resultado do Gate P2

- Regressão backend: 273 passed, 0 failed e 12 testes BYK deselecionados.
- Mobile: 8 testes Jest cobrem parsing do cliente P1, error envelope/mapping, URL configurável, enums PT-BR, ordem dos cinco ângulos e formatação de sinais.
- TypeScript strict: PASS. Expo Doctor: 20/20. Export Android: PASS, 1.574 módulos.
- Runtime Android: Pixel 7 AVD com Expo Go 57.0.9 abriu o app; health/status e estados online/offline foram confirmados contra a API P1 real.
- Fluxo integral sem aparelho: factory P1 com fake explícito criou sessão, capturou target #14/sample #15, retornou READY, comparação, diagnóstico, correção e pigmentos. O fake não integra o runtime do app.
- BYK real: connect AUTO retornou 503 controlado em `192.168.1.13:6000`; nenhuma leitura física foi solicitada.
- Auditoria: único `fetch` no API client; nenhum cálculo Lab/ΔE, regra de pigmento, grama, socket ou protocolo no mobile.
- Golden preservada com SHA-256 `a74672dbde168962bac4d5640d2c0edb2a08fe8e20ad7b01c0062e5a242d15ba`.

## Resultado do Gate P3

- Backend: 278 passed, 0 failed, 12 integrações BYK deselecionadas. Novos testes cobrem serialização do resultado do domínio, restart recovery com JSON temporário, abandono preservado, feedback e bloqueio de segundo pending.
- Mobile: 25 passed em 5 suites. Cobertura de vírgula decimal, ausência de dose automática, presets, múltiplos componentes, lock após aplicação, warnings, timeout, apresentação direta de response/outcomes, retry com mesmo ID/sem body de quantidade, ambiguidade de rede e restart recovery.
- TypeScript strict: PASS. Expo Doctor: 20/20. Android export e runtime Pixel 7: PASS.
- Isolamento: testes backend usam service/fake/TestClient/`tmp_path`, sem callback exportador. A factory de runtime foi somente in-memory; o botão AFTER não foi acionado e `data/` permaneceu vazio.
- Auditoria mobile em `app/` e `src/`: nenhuma fórmula AFTER−BEFORE, diferença de ΔE, `abs(beforeDelta)` ou quantidade/volume; somente o cliente central usa `fetch`.
- Golden original/cópia: byte-identical, SHA-256 `a74672dbde168962bac4d5640d2c0edb2a08fe8e20ad7b01c0062e5a242d15ba`.

## Resultado do Gate P4

- Backend: 290 passed, 0 failed, 12 integrações BYK deselecionadas.
- Mobile: 44 passed em 7 suites; TypeScript strict PASS; Expo Doctor 20/20; export Android PASS.
- Startup/recovery: offline sem crash, API≠BYK, sessão, operação preparada/em espera, pending prioritário, restart sem duplicar wait e 404 distinto de falha de rede.
- Concorrência: double target/sample prepare, double confirm e double AFTER prepare protegidos; confirmação ambígua reconciliada sem repetir ação física.
- Persistência: sessão/pending sobrevivem restart, escrita atômica, temporário limpo, corrupção preservada e servidor disponível em modo conservador.
- Observabilidade: health versionado, request ID em sucesso/erro e exceção inesperada sem detalhe sensível.
- Runtime Pixel 7: startup, tela offline/UNKNOWN e recusa de API incompatível exercitados. API P4 real respondeu health `0.4.0/v1` com request ID.
- Segurança de dados: testes usam temporários; `data/` vazio; nenhum AFTER, quantidade ou dataset fictício.
- Golden original/cópia: byte-identical, SHA-256 `a74672dbde168962bac4d5640d2c0edb2a08fe8e20ad7b01c0062e5a242d15ba`.
