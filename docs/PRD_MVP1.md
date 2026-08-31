# PRD — MANDACOR MVP 1

## Problema

A comparação de acabamento automotivo precisa associar duas novas leituras físicas inequívocas — alvo e amostra — e mostrar diferenças Lab por geometria, sem confundir registros antigos nem perder os dados brutos dos cinco ângulos.

## Usuário

Técnico colorista operando um espectrofotômetro BYK micro-5-color em bancada.

## Resultado esperado

Pela CLI ou API local, o técnico conecta o instrumento, faz uma nova leitura do alvo, faz outra da amostra, recebe `amostra - alvo` para L*, a*, b* e ΔE76 em 15°, 25°, 45°, 75° e 105°, e mantém uma sessão local auditável.

## Escopo

- Descoberta UDP e heartbeat do BYK.
- Conexão TCP e somente comandos de leitura comprovados.
- Informação do instrumento, lista e recuperação de medições.
- Snapshot e espera cancelável, com timeout, por medição realmente nova.
- Captura explícita de alvo e amostra na sessão.
- Validação dos 15 valores Lab obrigatórios.
- Cálculo puro de ΔL, Δa, Δb e ΔE76, sempre amostra menos alvo.
- Interpretação determinística com tolerâncias configuráveis.
- Necessidade de correção e candidatos qualitativos de pigmento com riscos explícitos.
- CLI `status`, `latest` e `compare`.
- Persistência JSON/JSONL local, com `schema_version: 1` e UUID de sessão.
- Testes unitários, de protocolo/parser, integração marcada e roteiro E2E.
- Descoberta automática em redes distintas e fallback por IP manual persistido, sem editar Python.
- Descoberta capaz de representar zero, um ou múltiplos instrumentos candidatos.
- API FastAPI local versionada, com OpenAPI, schemas próprios e lifecycle centralizado do instrumento.

## Fora do escopo

Cliente web, banco relacional, catálogo, alteração de fórmulas, dosagem de pigmentos, recomendação quantitativa, ML/IA, autenticação, multi-tenant, cloud e qualquer comando destrutivo ou de configuração/calibração do instrumento. A API local P1, o cliente mobile P2 e o workflow de ajuste P3 são parte do produto.

## Fluxo principal

1. CLI descobre e conecta o BYK.
2. Cria snapshot; solicita ao operador a leitura do alvo.
3. Detecta identidade nova, recupera, valida e associa como `target`.
4. Cria novo snapshot; solicita leitura da amostra.
5. Detecta outra identidade nova, recupera, valida e associa como `sample`.
6. Compara por ângulo e interpreta os deltas.
7. Exibe a tabela e persiste a sessão.
8. Desconecta e encerra o heartbeat, inclusive em erro/cancelamento.

## Estado incremental até o Gate 10

Conexão, captura e comparação estão implementadas. Diagnóstico, necessidade de correção e knowledge base qualitativa preservam sinais, conflitos e contexto. O modelo experimental registra quantidades e volumes exclusivamente informados pelo operador, captura AFTER nova e exporta target/before/after sem aprender efeito por grama. A implementação está validada offline; o Gate 10 permanece parcial porque nenhum trial físico real pôde ser executado.

## Estado do produto no Gate P1

O mesmo core está exposto por uma API FastAPI local versionada. Ela oferece saúde, lifecycle do instrumento, medições, sessões, operações de captura, comparação, diagnóstico, correção, candidatos qualitativos e workflow de ajustes. Schemas HTTP são separados do domínio, OpenAPI está disponível e quantidades continuam sendo exclusivamente informadas pelo operador. Na entrega original P1, o estado de sessão era in-memory; a persistência versionada e atômica foi adicionada no P4. Gate 10 permanece parcial e Gate 11 não foi iniciado.

## Estado do produto no Gate P2

Um app Android-first em React Native/Expo consome exclusivamente a API P1. Ele configura/testa o servidor, controla conexão, cria sessão, conduz TARGET/SAMPLE por operations, exibe os cinco ângulos e apresenta comparison/diagnosis/correction/pigment candidates. URL e IDs de retomada são persistidos localmente; o backend continua fonte da verdade. Não há Adjustment UI, cálculo científico, regra de pigmento ou dosagem no app. Gate 10 permanece parcial; Gate 11 e P3 não foram iniciados.

## Estado do produto no Gate P3

O app conduz BEFORE → ajuste informado pelo operador → AFTER com review e confirmação física explícitos. `PLANNED` não significa aplicado; após `APPLIED`, dados são somente leitura, timeout não autoriza reaplicação e retry conserva o mesmo ID/massas. Pending é recuperado no reinício, abandono é preservado, e resultado/histórico exibem exclusivamente cálculos recebidos do domínio pela API. Não há previsão de gramas, aprendizado ou ML. Gate 10 continua parcial por falta do trial físico real e Gate 11 não foi iniciado.

## Estado do produto no Gate P4

O MVP está endurecido para bancada: startup degradável, distinção API/BYK, configuração testável, reconciliação de sessão/captura/pending, suspensão segura, prevenção de ações duplicadas, persistência atômica, recovery conservador, versionamento, request IDs, error boundary e diagnóstico read-only. O projeto Android possui package/version estáveis e profiles interno/produção. A geração local do APK aguarda um JDK com compilador; o runtime em emulador e o bundle Android passaram. Gate 10 continua parcial por ausência de trial físico real e Gate 11 não foi iniciado.

## Requisitos invariantes

- O sinal é sempre `sample - target`.
- ΔE76 é complementar e nunca substitui os três deltas.
- Uma medição comparável tem exatamente os cinco ângulos requeridos e valores L/a/b numéricos finitos; faltas não viram zero.
- Alvo e amostra são associações explícitas, não posições implícitas na lista.
- Uma espera nunca retorna silenciosamente uma leitura presente no snapshot.
- Dados por ângulo permanecem armazenados individualmente.
- Rede é configuração, não código: `instrument_ip`, `discovery_address`, `local_interface`, `broadcast_address`, `tcp_port` e `udp_port` são conceitos distintos.
- Broadcast é derivado da interface e máscara reais; o sistema não presume `/24` nem troca simplesmente o último octeto por 255.
- No modo automático, o IP de origem de `BYKINSTRUMENT` deve ser validado como endpoint do instrumento; sem descoberta, o IP manual validado é o fallback.
- Uma lista com múltiplos instrumentos não pode ser reduzida silenciosamente ao primeiro candidato.

## Critérios de aceite

1. Descoberta, conexão e encerramento funcionam repetidamente na bancada.
2. Os cinco ângulos e 15 valores válidos são recuperados de XML real.
3. Timeout gera `NewMeasurementTimeoutError`; leitura incompleta gera `IncompleteMeasurementError`.
4. Testes demonstram os sinais e o ΔE76 corretos.
5. Target e sample têm identidades preservadas (serial, ID, GUID e timestamp quando disponíveis).
6. A saída apresenta todos os deltas e interpretações.
7. O JSON salvo contém versão, UUID, instrumento, leituras e comparação.
8. Testes de parser rodam sem instrumento; integração real fica isolada por marcador.
9. O fluxo E2E completo é repetido em bancada sem reutilizar leitura antiga.
10. O instrumento pode ser alcançado automaticamente ou por configuração manual, inclusive após mudança de sub-rede, sem alterar o fonte.
