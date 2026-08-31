# ADR 002 — Abstração de instrumentos

- Status: aceita; conexão e leitura implementadas, espera definida na aplicação no Gate 3
- Data: 2026-08-29

## Contexto

O MVP usa BYK, mas captura e comparação não devem depender de fabricante. Também é necessário definir precisamente o que significa "nova" medição.

## Decisão

Definir uma porta `InstrumentAdapter` com operações síncronas tipadas:

```python
discover() -> Sequence[DiscoveredInstrument]
connect(endpoint: InstrumentEndpoint | None = None) -> None
disconnect() -> None
get_info() -> InstrumentInfo
list_measurements() -> Sequence[MeasurementRef]
get_measurement(ref: MeasurementRef) -> Measurement
get_latest_measurement() -> Measurement
```

Tipos da porta não conterão XML nem estruturas BYK. `MeasurementRef` preserva ID, GUID e timestamp opcionais. `MeasurementSnapshot` é um conjunto imutável de identidades compostas disponíveis, não apenas o maior ID.

`DiscoveredInstrument` poderá conter fabricante, modelo, serial, IP, porta TCP e fonte/interface da descoberta. Zero candidatos permite fallback manual; um pode ser selecionado automaticamente; múltiplos são devolvidos integralmente para escolha futura.

O Gate 1 receberá uma configuração equivalente a:

```text
auto_discovery: bool
instrument_ip: str | None
discovery_address: str | None
local_interface: str | None
tcp_port: int = 6000
udp_port: int = 6002
discovery_timeout: float
connection_timeout: float
heartbeat_interval: float
poll_interval: float
```

Modo automático enumera interfaces adequadas, calcula discovery/broadcast com a máscara real, envia `BYKQUERY`, coleta todos os `BYKINSTRUMENT` e valida seus IPs de origem. Não presume `/24`. Se nada for descoberto e houver `instrument_ip` manual válido, tenta conexão direta com timeout controlado. A configuração deve sobreviver ao reinício sem edição de fonte.

`BykInstrumentAdapter` compõe descoberta/heartbeat, cliente TCP, framing, comandos e parser. Ele traduz falhas internas para exceções públicas específicas e converte XML em `Measurement` validada. Snapshot e wait não pertencem à porta nem ao adaptador: são operações de `MeasurementWaitService` na aplicação.

## Algoritmo de nova medição

1. Obter e congelar as referências atuais.
2. Em cada poll, listar novamente e calcular referências ausentes no snapshot.
3. Ordenar candidatos de modo determinístico usando timestamp/ID quando comparáveis, sem depender exclusivamente deles.
4. Recuperar candidato, validar identidade e todos os valores Lab.
5. Retornar apenas candidato inequivocamente novo.
6. Se cancelado, encerrar de forma explícita; se atingir deadline monotônico, lançar `NewMeasurementTimeoutError`.

Colisões, IDs reutilizados ou identidades insuficientes devem gerar erro/diagnóstico, nunca eleição silenciosa. A política exata será fechada no Gate 3 com dados reais.

## Ciclo de vida

O adaptador será context manager. `connect`/`disconnect` terão estados explícitos; `disconnect` será seguro em limpeza. Heartbeat inicia após descoberta confirmada e termina mesmo em erro. Uma única operação TCP por vez será protegida por lock, pois o protocolo de requisição/resposta não foi provado multiplexável.

## Erros públicos

`InstrumentNotFoundError`, `InstrumentConnectionError`, `InstrumentProtocolError`, `InstrumentTimeoutError`, `InvalidFrameError`, `CrcMismatchError`, `MeasurementNotFoundError`, `IncompleteMeasurementError` e `NewMeasurementTimeoutError`. Exceções mantêm encadeamento (`raise ... from error`).

## Alternativas rejeitadas

- Herança de uma grande classe base: cria acoplamento a detalhes que fabricantes podem não compartilhar.
- Retornar dicionários: enfraquece contratos e permite medição incompleta.
- Escolher as duas últimas leituras: não expressa intenção e reutiliza dados antigos.
- Asyncio no MVP: aumenta complexidade sem demanda de concorrência ampla.
- Um único campo `ip`: mistura endpoint TCP, destino de discovery e interface local.
- Retornar apenas o primeiro discovery: impede operação segura com múltiplos instrumentos.

## Resultado do Gate 1

A porta implementada expõe `discover`, `connect`, `disconnect`, `get_info` e `is_connected`. `discover` retorna lista e deduplica por serial quando disponível, ou endpoint IP+porta. Como o parser UDP mínimo não infere serial, a deduplicação BYK atual usa endpoint.

AUTO usa o IP retornado por `recvfrom`; zero resultados aciona `instrument_ip` e depois `last_known_instrument_ip`; múltiplos resultados exigem seleção explícita. MANUAL não executa discovery obrigatório. A configuração bem-sucedida persiste `last_known_instrument_ip` via porta de repositório.

## Extensão do Gate 2

A porta genérica ganhou `list_measurements`, `get_measurement`, `get_latest_reference` e `get_latest_measurement`. Nenhum nome de comando BYK aparece no contrato. `MeasurementReference` representa identidade leve; `Measurement` representa somente leitura completa e validada.

`get_latest_reference` e `get_latest_measurement` têm semânticas diferentes. A primeira retorna a maior referência BYK pelo critério documentado; a segunda tenta candidatos em ordem decrescente e ignora somente medições que falhem na validação/parsing, retornando a primeira válida ou erro explícito.

## Extensão do Gate 3

A porta não ganhou método específico de fabricante para espera. `MeasurementWaitService` cria um snapshot imutável de `(serial, ID, GUID)` e usa `list_measurements`/`get_measurement`. Quando GUID está ausente em um dos lados, ID mais serial é o fallback conservador; com ambos os GUIDs presentes, a mudança de GUID representa nova identidade.

Um candidato novo precisa aparecer em dois polls antes de sua única tentativa de recuperação. Essa janela de estabilização foi adicionada após observação real de que o BYK pode publicar o ID antes do conteúdo completo. Candidato inválido entra em `processed_candidates` e não é recuperado em loop; o serviço continua aguardando outra identidade nova válida até timeout.
