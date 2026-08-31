# ADR 001 — Arquitetura do MVP 1

- Status: aceita e implementada até o Gate P2; Gate 10 científico permanece parcial
- Data: 2026-08-29

## Contexto

O código comprovado concentra rede, protocolo, XML e apresentação. O MVP precisa preservar esse conhecimento e permitir novos instrumentos e interfaces sem contaminar a matemática colorimétrica.

## Decisão

Adotar uma arquitetura hexagonal leve, com dependências apontando para dentro:

- `domain`: dataclasses imutáveis, validação, comparação e interpretação puras.
- `application`: orquestra captura e sessão por portas, sem conhecer sockets, XML, BYK ou JSON.
- `instruments`: porta genérica e adaptador BYK; submódulos internos separam descoberta, framing, comandos e parsing.
- `storage`: porta de repositório e adaptador JSON.
- `cli`: adaptador de entrada/saída; apenas formata e chama casos de uso.
- `config`: centraliza configuração ambiental e defaults operacionais.
- `api`: adaptador FastAPI local, com schemas HTTP próprios e composição dos casos de uso existentes.
- `mobile`: adaptador React Native/Expo que consome somente contratos HTTP da API.

No Gate 1, `config` introduzirá um conceito equivalente a `InstrumentConnectionConfig`, fora do domínio colorimétrico, com `auto_discovery`, `instrument_ip`, `discovery_address`, `local_interface`, portas TCP/UDP, timeouts, heartbeat e poll interval. Este ADR registra o contrato; o Gate 0 não o implementa.

A descoberta será orientada pelas interfaces e máscaras reais. `instrument_ip` (endpoint TCP), `discovery_address` (destino do `BYKQUERY`), `local_interface` e `broadcast_address` não serão condensados em um campo ambíguo `ip`. Não se presume `/24`.

Usaremos `dataclass(frozen=True)` no domínio. O modelo é pequeno, deve permanecer sem dependências externas e não precisa do acoplamento de validação/serialização do Pydantic. Conversão JSON fica no adaptador.

Usaremos `threading` para heartbeat e polling bloqueante no MVP: o legado já prova esse modelo e sockets são bloqueantes. Cancelamento usará `threading.Event`; recursos usarão context manager e `finally`. Asyncio não traria benefício proporcional nesta CLI.

## Regras de dependência

Permitido:

- CLI → application/domain/config.
- Application → domain e portas abstratas.
- Adaptadores BYK/JSON → suas portas e domain.
- Composição na raiz → todas as implementações necessárias.

Proibido:

- Domain → socket, XML, BYK, JSON, CLI, framework web ou banco.
- Application → detalhes BYK, filesystem ou formatação de terminal.
- BYK parser/protocolo → CLI ou persistência.
- Storage → protocolo de instrumento.
- Domain → configuração de rede ou descoberta.

## Árvore final proposta

```text
mandacor/
├── pyproject.toml
├── README.md
├── .gitignore
├── docs/                         # documentos desta decisão e operação
├── legacy/
│   └── byk_reader_working.py         # golden reference imutável
├── data/sessions/.gitkeep
├── src/mandacor/
│   ├── config.py
│   ├── domain/
│   │   ├── measurement.py
│   │   ├── comparison.py
│   │   ├── interpretation.py
│   │   └── exceptions.py
│   ├── application/
│   │   ├── ports.py
│   │   └── comparison_session.py
│   ├── instruments/
│   │   ├── base.py
│   │   └── byk/
│   │       ├── discovery.py
│   │       ├── framing.py
│   │       ├── commands.py
│   │       ├── parser.py
│   │       ├── client.py
│   │       └── exceptions.py
│   ├── storage/
│   │   ├── base.py
│   │   └── json_repository.py
│   └── cli/main.py
└── tests/
    ├── unit/
    ├── protocol/
    ├── integration/
    ├── e2e/
    └── fixtures/{measurements,frames}/
```

Arquivos `__init__.py` serão adicionados onde necessários. Módulos serão criados apenas quando adquirirem responsabilidade real; por exemplo, um `crc.py` separado só se justifica se framing e testes não permanecerem coesos.

## Consequências

O core poderá ser chamado por CLI, API ou GUI e receber adaptadores futuros. Haverá algum código de mapeamento nas fronteiras, intencional para evitar dependências. A extração será incremental por gates, precedida por caracterização.

Configuração persistida será uma porta/adaptador de infraestrutura. A descoberta automática poderá retornar vários candidatos; seleção por interface humana permanece fora do Gate 1, mas o contrato não perderá candidatos.

## Implementação do Gate 1

O código foi organizado em `domain`, `ports`, `application` e `infrastructure`. O domínio conhece apenas `DiscoveredInstrument` e `InstrumentInfo`; sockets, XML, CRC, threads e JSON permanecem nos adaptadores. `InstrumentService` orquestra modos AUTO/MANUAL sem importar detalhes de framing.

A estrutura final do Gate 1 usa `src/mandacor/infrastructure/instruments/byk/` para constantes, CRC, framing, protocolo, discovery, heartbeat, cliente e adaptador. Não foram criados modelos nem casos de uso de medição do Gate 2.

## Implementação do Gate 2

O domínio agora contém `Measurement`, `LabValue`, `MeasurementAngle` e `MeasurementReference`, sem importar XML, rede ou BYK. A infraestrutura acrescenta DTO bruto, parser e mapper em módulos separados. O client traduz comandos em XML bruto; o adapter expõe somente objetos de domínio validados; application/CLI consomem a porta genérica.

Essa direção preserva o fluxo de dependência: BYK depende do domínio para produzir medições, mas o domínio não conhece o fabricante.

## Implementação do Gate 3

`MeasurementWaitService`, `MeasurementSnapshot` e `MeasurementIdentity` ficam na camada de aplicação. O serviço usa somente a porta genérica já existente (`list_measurements` e `get_measurement`) e concentra snapshot, polling síncrono, deadline monotônico, cancelamento cooperativo e política de candidatos. O domínio de medição não recebeu socket, XML, `Event`, relógio ou espera.

O adaptador BYK continua responsável apenas pela sessão e por traduzir respostas em objetos de domínio validados. A CLI compõe o serviço e apresenta `NEW MEASUREMENT DETECTED`; não existem conceitos de alvo, amostra ou comparação neste Gate.

## Implementação do Gate 4

`ColorSession` é um modelo imutável do core com UUID, criação, serial do instrumento, estado e papel `target` apontando para uma `Measurement` existente; valores Lab não são duplicados. `CaptureTargetService` fica na aplicação e separa `prepare_target_capture` (snapshot antes do prompt) de `capture_target` (wait, validação defensiva e substituição atômica).

A CLI depende do use case, que depende das operações genéricas de snapshot/wait. Sessão e target não conhecem BYK, XML, rede ou idioma de interface. Nenhuma operação de amostra ou comparação foi adicionada.

## Implementação do Gate 5

`ColorSession` ganhou o papel `sample` e estados coerentes de preparação/prontidão. `CaptureSampleService` espelha a fronteira transacional do target, mas exige target prévio, preserva-o por identidade de objeto e reutiliza integralmente `MeasurementWaitService`; não contém polling ou stabilization próprios.

`READY_FOR_COMPARISON` expressa apenas disponibilidade de duas Measurements válidas. Não existe modelo, função ou resultado de comparação. A CLI `session capture` orquestra target e sample na mesma conexão e mostra somente identidades/valores brutos.

## Implementação do Gate 6

`domain/comparison.py` contém somente modelos congelados, validação defensiva e matemática pura. `application/comparison_service.py` valida o estado da sessão e delega ao domínio; não possui porta de instrumento, repository, relógio ou efeitos colaterais.

A CLI read-only recebe explicitamente session UUID, target ID e sample ID, reidrata os papéis documentados e apenas formata o resultado. O domínio nunca arredonda e não conhece BYK. Nenhuma interpretação, tolerância, recomendação ou pigmento foi adicionada.

## Implementação do Gate 7

`domain/diagnosis.py` recebe somente `ColorComparison` imutável e produz enums/modelos imutáveis. Direções vêm do sinal do delta, eixo dominante vem das magnitudes por ângulo e resumos regionais preservam crossover sem média. Não existe application service porque nenhuma orquestração adicional é necessária.

A CLI traduz enums para PT-BR na apresentação; o domínio permanece independente de idioma, instrumento, arquivo, relógio e política de correção. Causas físicas, tolerância perceptual e recomendações não fazem parte desta camada.

## Implementação do Gate 8

`domain/correction.py` recebe `ColorDiagnosis` e `ColorComparison` e produz modelos congelados de necessidade de correção. A semântica vem do diagnóstico; a comparação fornece somente o vetor numérico inverso e a magnitude ΔE76. Identidades divergentes ou deltas inconsistentes são rejeitados.

Resumos regionais e globais preservam conflitos com `MIXED`; flags indicam apenas variação por ângulo. A CLI é presenter e adaptador de composição. O domínio de correção não conhece BYK, rede, XML, pigmentos, fórmulas, gramas ou ML.

## Implementação do Gate 9

`domain/pigments.py` é uma camada própria sobre `ColorCorrectionNeed`. Ela contém contexto de tinta, perfis regionais tipados, knowledge base versionada, proveniência e avaliação qualitativa. Não altera Measurement, Comparison, Diagnosis ou CorrectionNeed.

O avaliador percorre os cinco ângulos, classifica matches/conflicts/unknowns e aplica contraindicações antes de uma ordenação lexicográfica documentada. A base e a recomendação são imutáveis. Não há acesso a instrumento, arquivo, relógio, aleatoriedade, fórmula ou modelo quantitativo.

## Implementação do Gate 10

`domain/adjustments.py` contém modelos imutáveis, lifecycle e funções puras de response/outcome. `application/adjustment_workflow.py` coordena snapshot/wait e atualização atômica da sessão; `application/adjustment_dataset.py` mapeia e exporta CSV. O adaptador JSON de infraestrutura persiste apenas o pending aplicado para recovery.

O domínio reutiliza Comparison para BEFORE/AFTER contra o TARGET e não conhece BYK ou CSV. A aplicação reutiliza a porta genérica de medição e o mecanismo de estabilização existente. Quantidade e volume são fatos `Decimal` fornecidos pelo operador; nenhuma camada os prevê.

## Implementação do Gate P1

`api/app.py` oferece uma factory FastAPI injetável; `api/schemas.py` mantém Pydantic e JSON fora do domínio; `api/service.py` coordena lifecycle do instrumento, repositórios in-memory e operações de captura thread-safe. CLI e API são adaptadores paralelos sobre os mesmos serviços e modelos validados.

Import e health não conectam ao BYK. O processo admite um instrumento físico, e seu lifespan cancela operações e desconecta no shutdown. Bind e CORS são configuração de API separada da configuração de rede do instrumento. Nenhuma ciência do Gate 11 ou lógica quantitativa foi adicionada.

## Implementação do Gate P2

`mobile/` é um cliente Expo/TypeScript estrito. Expo Router organiza quatro telas e `MandacorApiClient` concentra URL, timeout, JSON e error envelope. O contexto mobile persiste somente URL/session/operation IDs e sempre revalida estado no backend.

O app inicia capturas pela sequência prepare → instrução → wait/poll, exibe respostas da API e faz apenas formatação visual de números/enums. Não calcula Lab/ΔE, não conhece protocolo BYK e não possui regras de pigmentos ou dosagem. A exceção Android para HTTP cleartext é explícita e limitada à necessidade da API local.
