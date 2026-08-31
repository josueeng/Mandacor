# Gate 0 — Resultado

## Status

**PASS**

A preservação, compilação, caracterização offline, execução read-only em bancada e validação de fixtures reais passaram. A primeira tentativa ocorreu com o instrumento desligado; o reteste com o instrumento ligado concluiu todo o fluxo. A golden reference não foi modificada.

## Golden reference

| Item | Resultado |
|---|---|
| Original | `conect_espectro.py` |
| Golden | `legacy/byk_reader_working.py` |
| SHA-256 original | `a74672dbde168962bac4d5640d2c0edb2a08fe8e20ad7b01c0062e5a242d15ba` |
| SHA-256 golden | `a74672dbde168962bac4d5640d2c0edb2a08fe8e20ad7b01c0062e5a242d15ba` |
| Byte identical | **YES** (`cmp` exit 0) |
| Golden reference modificada | **NO** |

Classificação: **CONFIRMADO POR TESTE**.

## Compilação

| Arquivo | Resultado |
|---|---|
| Original | **PASS** |
| Golden | **PASS** |

Classificação: **CONFIRMADO POR TESTE** com `python3 -m py_compile`.

## Protocolo

- UDP discovery: **CONFIRMADO EM CÓDIGO**, porta 6002, socket local efêmero.
- `BYKQUERY`: **CONFIRMADO EM CÓDIGO/TESTE**, 22 bytes, prefixo ASCII, dez zeros, inteiro 1 e porta local little-endian.
- `BYKINSTRUMENT`: **CONFIRMADO POR FIXTURE/EM BANCADA**, 104 bytes recebidos de `192.168.1.13:6002`.
- TCP: **CONFIRMADO EM BANCADA**, conexão de `192.168.1.11` para `192.168.1.13:6000`.
- Header: **CONFIRMADO EM CÓDIGO/TESTE**, 32 bytes, magic `47 42 03 00`, command ID no offset 20.
- CRC: **CONFIRMADO POR FIXTURE**, frame real de medição produz CRC `1054`, igual aos dois bytes recebidos.
- XML: **CONFIRMADO POR FIXTURE**, respostas reais dos três comandos foram extraídas e novamente analisadas offline.
- Delays de 200 ms e 700 ms: **CONFIRMADO EM CÓDIGO**; status de requisito do protocolo é **HIPÓTESE/PENDENTE DE VALIDAÇÃO**.

## Rede

- Uso atual de `192.168.1.1`: destino de `sendto(BYKQUERY, ..., 6002)` na descoberta e heartbeat; nunca usado em `bind`.
- É broadcast confirmado? **NO para a interface observada no Gate 0.**
- Evidência: **CONFIRMADO EM BANCADA**, host `192.168.1.11/24`, rota default `192.168.1.1`; broadcast da interface `192.168.1.255`.
- IP do instrumento recuperável via `recvfrom`? **YES nesta bancada.**
- Evidência: **CONFIRMADO EM BANCADA**, `addr[0]` foi `192.168.1.13` e a conexão TCP ao mesmo IP foi aceita. O legado ainda ignora `addr` e usa seu valor fixo.
- Qual envio causou a resposta, `.1` ou o fallback unicast anterior para `.13`? **UNKNOWN**; a golden executa ambos e a captura não atribui causalidade.

## Fixtures

Fixtures reais presentes: **16**, registradas com tamanho e SHA-256 em `tests/fixtures/byk/CAPTURE_METADATA.json`.

- `BYKQUERY.bin` e `BYKINSTRUMENT.bin`;
- requests e respostas TCP de informação, lista e medição;
- XML real dos três comandos;
- ACK, header, payload e CRC reais da medição;
- `measurement_real.json` com identidade e valores esperados.

Classificação: **REAL_CAPTURE / CONFIRMADO POR FIXTURE**. Nenhuma resposta foi fabricada ou sanitizada.

## Testes

| Item | Resultado |
|---|---:|
| Total selecionado offline | 22 |
| Passed | 22 |
| Failed | 0 |
| Skipped | 0 |
| Deselected (`instrument`) | 1 |

Instrument tests: uma execução manual read-only da golden foi realizada.

- Discovery: **PASS**.
- Heartbeat: **PASS** durante a sessão.
- TCP: **PASS**.
- `GetInstrumentInfo`: **PASS** — MicroTriColor, firmware `1.2.0.24448`.
- `RetrieveMeasurementIdList`: **PASS** — 3 registros.
- `RetrieveMeasurement`: **PASS** — ID 3.
- Leitura Lab: **PASS** — cinco ângulos e 15 valores.

## Medição real

| Campo | Valor confirmado por fixture |
|---|---|
| Measurement ID | 3 |
| GUID | `79bcbeb4-48e5-48cb-9162-6b3a0c26fca9` |
| Timestamp | `2026-08-27T11:29:13+00:00` |
| Nome | `Sample #3` |
| Temperatura | 29.604166 °C |

| Ângulo | L* | a* | b* |
|---:|---:|---:|---:|
| 15° | 77.1218414 | -0.81717968 | 1.26897097 |
| 25° | 57.4835281 | -0.799715519 | 0.563144684 |
| 45° | 30.4952812 | -0.602155924 | -0.0945866108 |
| 75° | 17.905941 | -0.205770135 | -1.66260004 |
| 105° | 13.9409418 | -0.318706036 | -2.96062827 |

## Dívida técnica

1. `192.168.1.1` está nomeado como broadcast, mas era gateway na rede observada.
2. O IP retornado por `recvfrom` é preservado, mas não dirige a conexão TCP.
3. Rede, IPs, portas e timeouts estão hardcoded.
4. `recv(4096)` pode consumir e descartar bytes do próximo frame coalescido.
5. A terminação depende da tag literal `</CommandResult>`.
6. Ausência Lab vira `None` e não erro no parser legado.
7. Ainda falta isolar experimentalmente se `.1` ou o fallback unicast `.13` provoca a resposta de discovery.

## Arquivos criados

- `legacy/byk_reader_working.py` e `legacy/README.md`;
- `pyproject.toml`;
- testes em `tests/characterization/` e `tests/integration/`;
- estrutura e README em `tests/fixtures/byk/`;
- 16 fixtures reais e `CAPTURE_METADATA.json`;
- `docs/GATE_0_REPORT.md`.

## Arquivos modificados

- `docs/CURRENT_IMPLEMENTATION_AUDIT.md`;
- `docs/PRD_MVP1.md`;
- `docs/ADR_001_ARCHITECTURE.md`;
- `docs/ADR_002_INSTRUMENT_ABSTRACTION.md`;
- `docs/BYK_PROTOCOL.md`;
- `docs/IMPLEMENTATION_PLAN.md`;
- `docs/TEST_STRATEGY.md`.

`docs/COLORIMETRY.md` foi revisado e não precisou de alteração: o Gate 0 não mudou regras colorimétricas.

## Gate 1 — não executado

Após aprovação explícita, o Gate 1 criará uma camada BYK separada da golden, configuração persistente de rede, descoberta multi-interface/multi-instrumento, fallback por IP manual validado, timeouts e os contratos do adaptador. Nenhuma dessas implementações foi criada agora.
