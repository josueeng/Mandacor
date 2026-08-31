# Gate 1 — Resultado

## Status

**PASS**

O driver modular, configuração dinâmica, AUTO, MANUAL, persistência, heartbeat, `GetInstrumentInfo`, buffer TCP e testes foram concluídos. Gate 2 não foi iniciado.

## Golden Reference

| Item | Resultado |
|---|---|
| Hash antes | `a74672dbde168962bac4d5640d2c0edb2a08fe8e20ad7b01c0062e5a242d15ba` |
| Hash depois | `a74672dbde168962bac4d5640d2c0edb2a08fe8e20ad7b01c0062e5a242d15ba` |
| Original/golden byte-identical | **YES** |
| Golden modificada | **NO** |

## Arquitetura

Camadas implementadas:

- `domain`: `DiscoveredInstrument`, `InstrumentInfo` imutáveis;
- `ports`: instrumento e repositório de configuração;
- `application`: `InstrumentService`;
- `infrastructure/config`: JSON schema v1 com gravação atômica;
- `infrastructure/instruments/byk`: discovery, heartbeat, cliente, protocolo, framing, CRC, exceções e adaptador;
- `__main__`: CLI minimalista de desenvolvimento.

Nenhum modelo ou serviço de medição do Gate 2 foi criado.

## Discovery automático

| Item | Evidência de bancada |
|---|---|
| Interface | `wlx78bdbc4c8ed5` |
| IPv4/máscara | `192.168.1.11/24` |
| Destino calculado | `192.168.1.255:6002` |
| `BYKINSTRUMENT` | **RECEBIDO** |
| Source IP | `192.168.1.13` |
| Resultado AUTO | **PASS** |

O endpoint TCP foi obtido de `addr[0]`; nenhum IP de instrumento está no código de produção. Discovery retorna lista e deduplica por serial ou IP+porta.

## Instrumento

| Campo | Resultado |
|---|---|
| Manufacturer | BYK |
| Model | MicroTriColor |
| Serial | 1327634 |
| Firmware | 1.2.0.24448 |
| IP | 192.168.1.13 |
| TCP | 6000 |

Classificação: **CONFIRMADO EM BANCADA**.

## Manual connection

Conexão direta pelo IP configurado, sem discovery obrigatório: **PASS**. O mesmo modelo, serial e firmware foram retornados. A CLI também persistiu a configuração em arquivo temporário.

## Configuração

| Caso | Resultado |
|---|---|
| AUTO | **PASS** |
| MANUAL | **PASS** |
| IP inválido antes do socket | **PASS** |
| IP alterável sem editar fonte | **PASS** |
| Persistência/reload schema v1 | **PASS** |
| AUTO → last known/manual fallback | **PASS** |
| Múltiplos candidatos | **PASS**, exige seleção |
| Portas/timeouts configuráveis | **PASS** |

Estratégia AUTO: discovery; se vazio, `instrument_ip`; depois `last_known_instrument_ip`; caso contrário, `InstrumentNotFoundError`.

## Heartbeat

| Item | Resultado |
|---|---|
| Start | **PASS** |
| Start duplicado | impedido/idempotente |
| Stop | **PASS** |
| Stop repetido | idempotente |
| Thread leak após disconnect | **NO** |

Vinte ciclos reais AUTO consecutivos confirmaram cleanup.

## Protocol Compatibility

| Item | Resultado |
|---|---|
| BYKQUERY versus fixture real | **PASS** |
| CRC versus frame real | **PASS** |
| Header/request GetInstrumentInfo | **PASS**, byte-identical |
| ACK + XML real | **PASS** |
| Semântica GetInstrumentInfo versus golden | **PASS** |
| Buffer com frames coalescidos | **PASS**, excedente preservado |
| Timings empíricos 200/700 ms | preservados e centralizados |

## Testes

| Conjunto | Resultado |
|---|---:|
| Gate 0 existentes | 22 passed |
| Gate 1 offline novos | 26 passed |
| Offline total | 48 passed, 0 failed |
| Integração modular read-only | 2 passed |
| Total executado aplicável | 50 passed, 0 failed |
| Default offline | 3 testes `instrument` deselecionados |
| Ciclos AUTO adicionais | 20/20 passed |

## Hardcodes

IP hardcoded em `src/mandacor`: **NO**.

Busca por `192.168.` e `10.0.` em produção: zero resultados. `6000` e `6002` aparecem somente em `byk/constants.py`; configuração pode sobrescrevê-los.

## Dívida técnica

1. Enumeração automática de interfaces usa `fcntl/ioctl` e é Linux/POSIX; outros sistemas precisam de provider.
2. XML ainda é delimitado por `</CommandResult>` por falta de comprimento comprovado.
3. O payload UDP não é interpretado além do prefixo; modelo/serial vêm de `GetInstrumentInfo`.
4. A heurística de interfaces virtuais é inicial e injetável.
5. Seleção entre múltiplos instrumentos ainda não possui UI, intencionalmente fora deste Gate.

## Arquivos modificados

- `pyproject.toml`;
- `docs/ADR_001_ARCHITECTURE.md`;
- `docs/ADR_002_INSTRUMENT_ABSTRACTION.md`;
- `docs/BYK_PROTOCOL.md`;
- `docs/IMPLEMENTATION_PLAN.md`;
- `docs/TEST_STRATEGY.md`.

## Arquivos criados

- pacote `src/mandacor/` com domínio, portas, serviço, configuração, CLI e driver BYK;
- testes Gate 1 em `tests/unit/`;
- integração modular em `tests/integration/test_byk_modular_instrument.py`;
- `docs/ADR_003_NETWORK_INTERFACE_DISCOVERY.md`;
- `docs/GATE_1_REPORT.md`.

## Gate 2 — não executado

Após aprovação explícita, o Gate 2 deverá adicionar listagem e recuperação, modelo `Measurement`, validação dos cinco ângulos e dos 15 valores Lab. Nenhuma dessas funcionalidades foi implementada no Gate 1.
