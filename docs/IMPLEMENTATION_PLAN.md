# Plano de implementação por gates

Cada gate termina com evidência, revisão humana e autorização antes do seguinte. Falha de bancada não será contornada por suposição de protocolo.

## Gate 0 — Preservação e caracterização

Entregas: copiar byte a byte `conect_espectro.py` para `legacy/byk_reader_working.py`; registrar hashes; criar `pyproject.toml`, esqueleto mínimo de testes e fixtures sanitizadas de XML/frames reais; escrever testes de caracterização para consulta UDP, header, CRC, requests e parsing existente. Não refatorar a golden reference.

Aceite: hashes fonte/cópia iguais; golden reference compila e continua conectando em bancada; fixtures têm origem documentada e testes passam offline. **STOP.**

Resultado em 2026-08-29: preservação, compilação, testes offline, captura real e fluxo read-only em bancada passaram após o instrumento ser ligado. Status do Gate 0: **PASS**. **STOP**, aguardando aprovação humana antes do Gate 1.

## Gate 1 — Descoberta e conexão

Entregas: nova camada BYK desacoplada da golden reference; `InstrumentAdapter`; configuração de conexão e repositório de configuração; validação de IP; descoberta/heartbeat automáticos por interfaces e máscaras reais; fallback por IP manual; `discover` retornando zero, um ou múltiplos instrumentos; `connect`, `get_info`, `disconnect`, timeouts, logging e testes com sockets falsos. Trocar de rede não exigirá editar Python.

Aceite: nenhuma escrita destrutiva; limpeza garantida; informação corresponde ao legado; 20 ciclos reais consecutivos bem-sucedidos, ou critério substituto formalmente aprovado e registrado. **STOP.**

Casos obrigatórios:

1. Auto discovery encontra instrumento, obtém IP e conecta TCP.
2. Auto discovery não encontra; IP manual configurado conecta diretamente.
3. Mudança de `192.168.1.44` para `192.168.0.55` ocorre sem alterar fonte.
4. `999.999.1.1` é rejeitado antes da rede.
5. IP válido indisponível termina em timeout controlado.
6. Configuração persiste e é recuperada após reinício.
7. Dois ou mais BYK produzem múltiplos candidatos; seleção por UI pode vir depois.
8. Broadcast/discovery é calculado pela máscara real; nenhum algoritmo presume `/24`.

Resultado em 2026-08-29: **PASS**. AUTO e MANUAL passaram no instrumento; 20 ciclos AUTO consecutivos passaram; configuração JSON, validação, multi-interface, múltiplos candidatos, heartbeat e buffer persistente estão cobertos. **STOP**, aguardando aprovação antes do Gate 2.

## Gate 2 — Leitura existente

Entregas: modelos de medição, parser BYK, `list_measurements`, `get_measurement`, `get_latest_measurement`; testes com XML real de sucesso/erro/incompleto.

Aceite: recupera ID/GUID/timestamp e exatamente os cinco ângulos com L/a/b finitos; incompleto falha explicitamente; resultado confere com golden reference. **STOP.**

Resultado em 2026-08-29: **PASS**. Listagem, retrieve, modelo imutável, validação, latest valid, CLI e integração dos três registros passaram. Foram concluídos 20/20 ciclos read-only com timeout 1,5 s. **STOP**, aguardando aprovação antes do Gate 3.

## Gate 3 — Detecção de nova leitura

Entregas: snapshot por identidade composta; polling com deadline monotônico, intervalo configurável, cancelamento e `wait_for_new_measurement`.

Aceite: testes provam que leitura anterior nunca retorna; nova leitura retorna uma vez; timeout/cancelamento encerram com erro claro; validação em bancada. **STOP.**

Resultado em 2026-08-29: **PASS**. Snapshot composto, espera síncrona, deadline monotônico, cancelamento, estabilização de candidato, erros transitórios limitados, CLI e política de primeira nova válida foram implementados. O timeout real não devolveu leitura antiga; três ciclos reais retornaram IDs distintos 6, 8 e 9. O ID 7 apareceu incompleto durante a espera e foi descartado, como especificado. Heartbeat permaneceu ativo durante as esperas e encerrou após disconnect. **STOP**, sem iniciar o Gate 4.

## Gate 4 — Captura do alvo

Entregas: caso de uso que tira snapshot, aguarda uma nova leitura válida e a associa explicitamente como `target` em sessão com UUID.

Aceite: alvo não pode ser leitura pré-existente; identidade e 15 valores ficam preservados; erros propagam contexto. **STOP.**

Resultado em 2026-08-29: **PASS**. O Pre-Gate confirmou que o ID 7 ficou completo e endureceu o Gate 3 com retry limitado de estabilização; uma leitura real, ID 10, foi recuperada na segunda tentativa do mesmo ID. `ColorSession`, `CaptureTargetService`, preparo antes do prompt, recaptura transacional e CLI `target capture` foram implementados. Timeout real manteve target vazio; captura real associou somente a nova Measurement ID 12 ao papel target. **STOP**, sem iniciar Gate 5.

## Gate 5 — Captura da amostra

Entregas: novo snapshot após o alvo; captura e associação explícita como `sample`; estado de sessão impede ordem inválida.

Aceite: amostra é posterior/nova em relação ao snapshot e distinta do alvo; timeout não reutiliza alvo. **STOP.**

Resultado em 2026-08-29: **PASS**. `ColorSession` passou a suportar sample e os estados `WAITING_FOR_SAMPLE`/`READY_FOR_COMPARISON`; `CaptureSampleService` exige target, usa snapshot + wait endurecido e preserva target/sample anterior em falha. Timeout real manteve target 12 e sample vazia. Captura real associou sample ID 13 à mesma sessão, mantendo target 12 e cinco ângulos/15 Lab. **STOP**, sem iniciar Gate 6.

## Gate 6 — Comparação matemática

Entregas: objetos e funções puras de comparação por ângulo, sem interpretação ou tolerâncias neste Gate.

Aceite: todos os ângulos calculam `sample - target`; exemplos de sinal, negativos relativos, precisão, ΔE76 e medição incompleta estão cobertos. **STOP.**

Resultado em 2026-08-29: **PASS**. `AngleComparison`, `ColorComparison`, `compare_measurements` e `compare_session` foram implementados sem I/O ou dependência BYK. Vinte testes novos cobrem sinais, zero, vetores conhecidos, cinco ângulos independentes, precisão, identidade, imutabilidade, dados inválidos e estados. A sessão real documentada target 12/sample 13 foi comparada read-only e o ângulo 15° conferiu por cálculo independente. **STOP**, sem iniciar Gate 7.

## Gate 7 — Diagnóstico colorimétrico determinístico

Entregas: `AngleDiagnosis`, `ColorDiagnosis`, enums fortes, eixo dominante, pior ângulo/ranking, resumos front/mid/flop e padrões simples de sinal.

Aceite: os cinco ângulos reais produzem direções esperadas, crossovers não são ocultados por média, nenhuma tolerância perceptual ou recomendação é criada. **STOP.**

Resultado em 2026-08-29: **PASS**. Diagnóstico puro e imutável foi implementado sobre `ColorComparison`. Dezenove testes novos cobrem sinais, absolutos negativos, dominante/tie, ranking, regiões, padrões, tendência e dados reais. A CLI read-only confirmou o diagnóstico da sessão 12/13. **STOP**, sem iniciar Gate 8.

## Gate 8 — Necessidade de correção colorimétrica

Entregas: ações tipadas por eixo e ângulo, vetor Lab inverso, resumos front/mid/flop, uniformidade global, flags neutras de mismatch e prioridade herdada do pior ângulo/eixo dominante.

Aceite: inversões semânticas e numéricas corretas, cinco ângulos preservados, conflitos nunca ocultados por média, nenhum pigmento/grama/causa física e inputs imutáveis. **STOP.**

Resultado em 2026-08-29: **PASS**. `AngleCorrectionNeed`, `ColorCorrectionNeed` e `derive_correction_need` foram implementados como domínio puro. Vinte e um testes novos cobrem todas as inversões, vetor, regiões, uniformidade, flags, prioridade, caso real e mutação. Suíte offline: 176 passed. A tentativa opcional de apresentação read-only encontrou o instrumento indisponível por timeout; nenhuma leitura física era exigida pelo Gate. **STOP**, sem iniciar Gate 9.

## Gate 9 — Knowledge base e seleção qualitativa de pigmentos

Entregas: `PaintContext`, perfis regionais com proveniência, base Skylack/Skymix versionada, riscos/contraindicações, avaliação multiângulo explicável e CLI com contexto obrigatório.

Aceite: códigos exigidos cadastrados, unknown nunca tratado como neutral, BP203 bloqueado em metálico/pérola, ranking determinístico sem score e nenhuma dosagem. **STOP.**

Resultado em 2026-08-30: **PASS**. Foram cadastrados 31 perfis; 20 possuem conhecimento empírico explicitamente fornecido e 11 alumínios BP261–BP271 permanecem unknown. Vinte e quatro testes novos validam perfis, regras gerais isoladas, contexto, segurança, seleção e caso real. Suíte offline: 200 passed. **STOP**, sem iniciar Gate 10.

## Gate 10 — Histórico experimental BEFORE → ADJUSTMENT → AFTER

Entregas: componentes/massas/volume informados pelo operador, pending recuperável, captura AFTER por snapshot+wait, observed response, outcomes por eixo/ΔE, histórico imutável e CSV principal/normalizado.

Aceite: toda a validação offline mais pelo menos um trial físico real controlado. **STOP.**

Resultado em 2026-08-30: **PARTIAL**. Cinquenta e dois testes novos elevaram a suíte para 252 passed e validaram domínio, lifecycle, recovery, atomicidade e dataset. O trial físico obrigatório não foi executado porque a tinta/base física correspondente ao BEFORE #13 não estava disponível. Nenhum pending, massa, AFTER ou linha experimental foi criado. **STOP**, sem iniciar Gate 11.

## Gate P1 — API local do MVP

Entregas: factory FastAPI injetável, schemas/erros HTTP próprios, lifecycle centralizado do BYK, sessões/operações thread-safe em memória, endpoints de medição/captura/ciência/pigmentos/ajustes, OpenAPI, CORS explícito e comando `mandacor api serve`.

Resultado em 2026-08-30: **PASS**. Os 252 testes anteriores permaneceram verdes e 21 testes de API elevaram a suíte a 273 passed, com 12 integrações de instrumento deselecionadas. Golden intacta. O smoke BYK read-only foi tentado, mas a conexão em `192.168.1.13:6000` estava indisponível; o instrumento real é opcional neste Gate e nenhuma captura foi solicitada. Gate 10 permanece **PARTIAL**; Gate 11 e Gate P2 não foram iniciados. **STOP.**

## Gate P2 — somente plano

Criar um shell React Native/Expo que consuma a API P1 e trate seus códigos de erro/operação. Não duplicar ciência, acesso BYK ou cálculo de quantidade no cliente.

Resultado em 2026-08-30: **PASS**. Expo SDK 57/React Native 0.86/TypeScript strict, quatro abas, cliente HTTP central, persistência de IDs, lifecycle de captura e resultados foram implementados. Oito testes mobile, typecheck, Expo Doctor 20/20, bundle Android e execução no Pixel 7 passaram. A API real confirmou health/status/offline; o BYK permaneceu indisponível, e o fluxo integral foi validado explicitamente contra a factory P1 com fake de teste. Os 273 testes backend e o Golden permaneceram intactos. **STOP.**

## Gate P3 — workflow de ajuste mobile

Resultado em 2026-08-30: **PASS**. Formulário/review/confirmação física, bloqueio após aplicação, AFTER via operation existente, timeout/retry seguro, recuperação após reinício, abandono explícito, resultado, feedback e histórico foram implementados. A API recebeu extensões mínimas sem mover ciência para HTTP. Suíte backend: 278 passed; mobile: 25 passed; typecheck, Expo Doctor, export e Pixel 7 passaram. Nenhum dado sintético entrou em `data/`. Gate 10 permanece **PARTIAL** e Gate 11 **NOT STARTED**. **STOP.**

## Gate P4 — production readiness / UX hardening

Resultado em 2026-08-30: **PASS**. Startup controlado, estados tri-state, Central de Conexão, recuperação de sessão/operação/pending, lifecycle de polling, guardas contra double-submit, reconciliação de confirmação ambígua, persistência JSON atômica, corrupção segura, request IDs, compatibilidade v1, error boundary, doctor read-only e packaging Android foram concluídos. Backend: 290 passed; mobile: 44 passed; typecheck, Doctor, export e runtime Pixel 7 passaram. O APK local ficou bloqueado porque não há `javac`, com procedimento documentado. Gate 10 permanece **PARTIAL** e Gate 11 **NOT STARTED**. **STOP.**

## Gate P5 — somente plano

Instalação/distribuição interna e operação piloto. Não executado.

## Ordem de decisões pendentes

1. No Gate 3, fechar identidade composta e política para IDs reutilizados.
2. Em gate futuro de persistência, escolher JSON por sessão ou JSONL com base em operação/recuperação desejada.
