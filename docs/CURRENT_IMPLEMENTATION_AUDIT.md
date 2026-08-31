# Auditoria da implementação atual

## Escopo e método

Auditoria realizada em 2026-08-29 antes de qualquer refatoração. A busca cobriu todo o diretório por `BYKQUERY`, `BYKINSTRUMENT`, portas 6000/6002, comandos conhecidos, CRC/XMODEM, magic e `CommandResult`. O arquivo foi lido integralmente e validado com `python3 -m py_compile`.

No reconnaissance, o diretório não continha repositório Git, manifesto de dependências, testes, fixtures ou outros arquivos-fonte. Portanto, não há histórico local que permita provar quando o código foi executado em bancada. O Gate 0 adicionou somente preservação, testes e documentação.

## Inventário

| Arquivo | Responsabilidade | Estado | Observação |
|---|---|---|---|
| `conect_espectro.py` | Descoberta/heartbeat UDP, conexão TCP, framing, CRC, comandos, parsing e exibição | funcional segundo o relato; monolítico/legado | 1.115 linhas, SHA-256 `a74672dbde168962bac4d5640d2c0edb2a08fe8e20ad7b01c0062e5a242d15ba`, somente biblioteca padrão |
| `legacy/byk_reader_working.py` | Golden reference congelada | byte a byte idêntica | mesmo SHA-256; `cmp` bem-sucedido em 2026-08-29 |
| `tests/characterization/` | Caracterização offline | ativo | dados não reais rotulados `SYNTHETIC_TEST_DATA` |
| `tests/fixtures/byk/` | Destino de capturas reais | pendente | nenhuma captura real foi inventada |

Nenhuma duplicação de implementação foi encontrada. O nome `conect_espectro.py` é o único artefato com conhecimento do protocolo.

## Fluxo atual catalogado

1. `DiscoveryHeartbeat.start()` cria socket UDP, habilita broadcast, liga em porta efêmera e monta a consulta com essa porta.
2. Envia `BYKQUERY` para `192.168.1.1:6002`; tenta até cinco vezes e usa unicast para `192.168.1.13:6002` como fallback.
3. Aceita datagrama iniciado por `BYKINSTRUMENT` e inicia uma thread daemon.
4. A thread repete a consulta em ciclo de aproximadamente 1 segundo e atualiza `last_response`.
5. O fluxo principal abre TCP para o IP fixo `192.168.1.13`, porta 6000, e espera 700 ms.
6. `transact()` envia header de 32 bytes, espera 200 ms, envia XML UTF-8 mais CRC e lê até quatro mensagens procurando resposta de dados.
7. `recv_message()` valida magic e CRC; diferencia ACK pelo bit `0x1000`; para dados, acumula até `</CommandResult>` e mais dois bytes de CRC.
8. Executa `GetInstrumentInfo` (ID 4), `RetrieveMeasurementIdList` (ID 143) e `RetrieveMeasurement` (ID 42).
9. Para obter a última leitura, ordena IDs de forma decrescente e ignora registros cuja recuperação retorne erro.
10. O parser extrai `L*`, `a*` e `b*` para 15°, 25°, 45°, 75° e 105°, mas permite `None`, e a CLI apenas os imprime.
11. O `finally` encerra heartbeat e socket UDP; o context manager encerra TCP.

## O que preservar exatamente no Gate 0

- O arquivo inteiro, byte a byte, como `legacy/byk_reader_working.py`, acompanhado do hash acima.
- A construção atual do datagrama de descoberta, inclusive endianess e porta UDP local embutida.
- O layout e os valores constantes do header.
- A separação temporal entre header e corpo na transmissão.
- A ordem ACK/resposta tolerada por `transact()`.
- CRC sobre `header + payload`, XMODEM com init zero e saída big-endian.
- IDs, nomes, XML e grafia dos parâmetros dos três comandos de leitura.
- O caminho XML de LAB e os nomes como `L* 15`.
- O fallback por IDs anteriores quando um registro não pode ser recuperado.

Nada disso deve ser "embelezado" antes de testes de caracterização e fixtures reais.

## Candidatos a refatoração posterior

- Separar transporte, framing, comandos, parser, adaptador e apresentação.
- Injetar configuração, relógio/sleep, sockets e logger para permitir testes.
- Usar o IP respondente da descoberta, após confirmação em bancada, em vez de IP fixo.
- Substituir `print()` por logging estruturado fora da golden reference.
- Traduzir erros genéricos em exceções específicas sem mascarar a causa.
- Fazer parsing e validação estritos em um modelo de domínio.
- Tornar recepção robusta a fragmentação/coalescência TCP, somente com frames reais como caracterização.

## Dívida técnica e riscos

| Risco | Impacto | Mitigação planejada |
|---|---|---|
| IP do instrumento e endereço de broadcast fixos | falha fora da rede atual; descoberta não governa conexão | configuração central e teste do IP retornado no Gate 1 |
| O reconnaissance começou sem fixtures/tráfego bruto | regressões de protocolo poderiam passar despercebidas | mitigado no Gate 0 para fluxos de sucesso; faltam respostas de erro reais |
| Delimitação XML por tag literal | namespaces, whitespace ou framing diferente podem quebrar leitura | caracterizar respostas reais antes de mudar framing |
| `sock.recv(4096)` pode consumir bytes do próximo frame | dessincronização em TCP coalescido | fixtures de stream fragmentado/coalescido e buffer persistente |
| Não há timeout próprio de nova medição | risco de reutilizar leitura antiga no futuro | snapshot e polling explícitos no Gate 3 |
| LAB ausente vira `None` | dados incompletos podem atravessar o legado | `IncompleteMeasurementError` na fronteira do domínio |
| XML sem defesa contra entradas hostis | risco de consumo de recursos, embora instrumento seja confiável | limites de payload e parser endurecido após caracterização |
| Thread daemon e estado reutilizável não reinicializado | ciclo start/close repetido pode falhar | ciclo de vida idempotente no novo adaptador |
| Pausas mágicas de 200/700 ms | sensibilidade a firmware/rede | manter inicialmente, medir timings, tornar configurável |
| Ausência de controle de versão | baixa rastreabilidade | inicializar Git somente com autorização do responsável |

## Dependências

O legado depende apenas de `binascii`, `socket`, `struct`, `threading`, `time`, `xml.etree.ElementTree` e `typing`, todos da biblioteca padrão. Depende operacionalmente da rede local, do BYK em endereços fixos e dos timings do firmware.

## Lacunas que exigem bancada

- Confirmar o conteúdo completo da resposta `BYKINSTRUMENT` e como extrair IP/modelo/serial.
- Confirmar se `192.168.1.1` é broadcast dirigido da rede ou particularidade do ambiente.
- Capturar variações reais de fragmentação/coalescência e ordem; um fluxo completo de sucesso já foi preservado.
- Confirmar limites, wraparound e estabilidade de ID/GUID/timestamp.
- XMLs de sucesso foram confirmados; ainda faltam capturas reais de erro, registro órfão e LAB incompleto.

## Evidência adicional do Gate 0

### Rede atual e `192.168.1.1`

- **CONFIRMADO EM CÓDIGO:** `BROADCAST_IP = "192.168.1.1"` ocorre uma vez, na linha 17. O valor é usado como destino de `sock.sendto(query, (BROADCAST_IP, 6002))` durante descoberta (linha 87) e heartbeat (linhas 140–143).
- **CONFIRMADO EM CÓDIGO:** o socket UDP liga em `0.0.0.0` e porta efêmera; `recvfrom(4096)` recebe `(data, addr)` nas linhas 93 e 152. Quando o prefixo é reconhecido, o par completo é guardado em `last_response`.
- **CONFIRMADO EM BANCADA:** durante a execução do Gate 0, a interface ativa era `192.168.1.11/24`, a rota default apontava para `192.168.1.1` e o broadcast correspondente a essa interface é `192.168.1.255`. Portanto, nesta rede/execução, `.1` era gateway, não o endereço de broadcast da interface.
- **PENDENTE DE VALIDAÇÃO:** por que o código comprovado usa o gateway como `BROADCAST_IP` e se essa topologia encaminha discovery em outra condição.
- **CONFIRMADO EM CÓDIGO:** o endereço-fonte retornado por `recvfrom` fica disponível em `addr` e é impresso na descoberta inicial.
- **CONFIRMADO EM BANCADA:** no reteste, `addr[0]` foi `192.168.1.13`, o mesmo endpoint que aceitou a conexão TCP.
- **CONFIRMADO EM CÓDIGO:** apesar dessa evidência, o legado continua ignorando `addr[0]` e conectando por `DEVICE_IP` fixo.

### Execução read-only do Gate 0

- **CONFIRMADO EM BANCADA:** a golden abriu o socket e enviou `BYKQUERY` pela porta UDP local 47424.
- **CONFIRMADO EM BANCADA:** a primeira tentativa não recebeu `BYKINSTRUMENT`; posteriormente o usuário confirmou que o instrumento estava desligado.
- **CONFIRMADO EM BANCADA:** com o instrumento ligado, discovery, heartbeat, TCP, os três comandos e leitura Lab passaram.
- **CONFIRMADO POR FIXTURE:** 16 artefatos reais preservam discovery, streams TCP, XMLs, CRC e a medição ID 3.
- **PENDENTE DE VALIDAÇÃO:** causalidade do destino de discovery. O laço envia a `.1` e também faz fallback unicast para `.13`; a sessão não isolou os destinos.
