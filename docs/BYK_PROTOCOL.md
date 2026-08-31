# Protocolo BYK observado

Este documento descreve somente evidência presente em `conect_espectro.py`, relatado como funcional em equipamento real. A golden reference e capturas futuras prevalecem sobre este texto.

## CONFIRMADO EM CÓDIGO

### Descoberta e heartbeat UDP

- Destino configurado: `192.168.1.1:6002`.
- Fallback unicast configurado: `192.168.1.13:6002`.
- Socket local liga em `0.0.0.0` e porta efêmera, com `SO_BROADCAST`.
- Consulta de 22 bytes:

```text
offset  tamanho  conteúdo
0       8        ASCII BYKQUERY
8       10       zeros
18      2        inteiro 1, little-endian
20      2        porta UDP local, little-endian
```

- Uma resposta é reconhecida quando começa com ASCII `BYKINSTRUMENT`.
- Há até cinco tentativas iniciais.
- Após descoberta, uma thread envia a consulta aproximadamente a cada 1 segundo (janela de recepção de ~0,45 s mais espera de ~0,55 s).

### Transporte TCP

- IP atual: `192.168.1.13`; porta 6000; timeout 12 s.
- O firmware recebe uma pausa de 700 ms após conexão.
- Cada requisição envia primeiro o header, espera 200 ms e depois envia XML + CRC.

### Header de 32 bytes

Produzido por concatenação abaixo; inteiros são `uint32` little-endian:

```text
offset  tamanho  valor observado
0       4        47 42 03 00 (ASCII GB + 03 00)
4       4        0 (flags na requisição)
8       4        1
12      4        11
16      4        0
20      4        command_id
24      4        0
28      4        0xFFFFFFFF
```

Nas respostas, o código interpreta o inteiro do offset 4 como flags e considera `flags & 0x1000` um ACK de aplicação. O ID de comando é lido no offset 20.

### XML e CRC

- XML é UTF-8, iniciado por declaração XML.
- Comando sem parâmetro usa elemento `Command` autocontido; com parâmetro usa `Parameters`.
- CRC: CRC-16/CCITT XMODEM, polinômio 0x1021, init 0x0000, implementado por `binascii.crc_hqx(data, 0)`.
- Entrada do CRC: header completo concatenado ao XML; saída de dois bytes big-endian.
- ACK possui header seguido diretamente de CRC.
- Resposta de dados é delimitada no legado pela primeira ocorrência de `</CommandResult>`, seguida por dois bytes de CRC.
- A transação lê até quatro mensagens e retorna a primeira resposta de dados válida.

### Comandos de leitura

| ID | Nome | Parâmetro | Extração atual |
|---:|---|---|---|
| 4 | `GetInstrumentInfo` | nenhum | todo elemento com atributos `Name` e `Value` |
| 143 | `RetrieveMeasurementIdList` | nenhum | elementos `.//Guid`: `Id`, `Name`, `Value` |
| 42 | `RetrieveMeasurement` | `ParameterInt32 Name="JobListRecordId" Value="..."` | `MeasureValue`, temperatura e coleção LAB |

Para LAB, o caminho é `DataValueCollection[@Name="LAB"]/ScaleValue` e as chaves esperadas são `L* N`, `a* N`, `b* N`, com N em 15, 25, 45, 75 e 105. Um `Result` diferente de `OK` é tratado como falha da recuperação.

## Divergências ou precisões relevantes

- A descrição geral diz "broadcast"; o código não usa `255.255.255.255`, mas `192.168.1.1`. Não alterar sem conhecer a topologia/captura real.
- A descoberta recebe o endereço do instrumento, mas o TCP usa IP fixo; não está comprovado no repositório que o payload UDP seja necessário para selecionar endpoint.
- "Header + XML + CRC" descreve a mensagem lógica, mas a transmissão comprovada separa header e corpo por 200 ms.

### Análise precisa de `192.168.1.1`

- **CONFIRMADO EM CÓDIGO:** a constante chama-se `BROADCAST_IP`, está na linha 17 e tem valor `192.168.1.1`.
- **CONFIRMADO EM CÓDIGO:** ela nunca é usada em `bind`; é destino UDP de `sendto` na descoberta inicial e no heartbeat, sempre na porta 6002.
- **CONFIRMADO EM CÓDIGO:** `SO_BROADCAST` é habilitado, mas o destino continua sendo explicitamente `.1`.
- **CONFIRMADO EM BANCADA:** na rede observada no Gate 0, o host era `192.168.1.11/24`, `.1` era a rota default e o broadcast da interface era `.255`. Assim, `.1` não era broadcast nessa execução.
- **HIPÓTESE:** o gateway pode encaminhar/responder ao mecanismo em alguma topologia, ou o nome/valor pode refletir uma configuração histórica. Não há captura para decidir.

### `recvfrom` e IP de origem

- **CONFIRMADO EM CÓDIGO:** as duas recepções usam `data, addr = sock.recvfrom(4096)`. O código guarda `(data, addr)` e imprime `addr` na descoberta inicial.
- **CONFIRMADO EM CÓDIGO:** o valor não alimenta `DEVICE_IP`; o TCP continua fixo em `192.168.1.13`.
- **CONFIRMADO EM BANCADA:** `addr[0]` observado foi `192.168.1.13`, igual ao endpoint TCP que aceitou conexão.

## HIPÓTESES E PENDÊNCIAS

- Significado dos campos do header além de flags e command ID.
- Estrutura integral do datagrama `BYKINSTRUMENT`.
- Se o heartbeat precisa usar exatamente o mesmo socket/porta da descoberta.
- Se todas as respostas terminam literalmente em `</CommandResult>` e se podem chegar frames coalescidos.
- Quantidade/ordem possível de ACKs e respostas além do limite empírico de quatro.
- Semântica, monotonicidade e eventual reutilização de measurement ID/GUID.
- Codificação e namespaces em outras versões de firmware.

## Operações permitidas no MVP

Somente descoberta, heartbeat, leitura de informação, listagem e recuperação. Não enviar exclusão, escrita de configuração, firmware ou alteração de calibração.

## CONFIRMADO POR TESTE DE CARACTERIZAÇÃO

- `BYKQUERY` tem 22 bytes e porta local little-endian.
- Headers dos IDs 4, 42 e 143 mantêm magic, tamanho e campos atuais.
- O CRC XMODEM produz `0x31c3` para o vetor canônico sintético `123456789` e cobre `header + XML` nos requests construídos.
- ACK sintético com flag `0x1000` é reconhecido e validado.
- XML sintético fragmentado é acumulado até a tag literal.
- O teste caracteriza a dívida existente: se XML+CRC e o frame seguinte chegam no mesmo `recv(4096)`, os bytes excedentes são consumidos e descartados. **DÍVIDA TÉCNICA PARA GATE 1/2.**
- Parser sintético preserva cinco ângulos e 15 valores; se `b* 105` falta, o legado produz `None` sem erro. A rejeição pertence ao Gate 2.

## Resultado de bancada do Gate 0

- **CONFIRMADO EM BANCADA:** a primeira tentativa não recebeu resposta porque o instrumento estava desligado, conforme confirmação do usuário.
- **CONFIRMADO EM BANCADA:** no reteste, `BYKINSTRUMENT` de 104 bytes chegou de `192.168.1.13:6002`; TCP conectou em `192.168.1.13:6000`.
- **CONFIRMADO EM BANCADA:** cada um dos três comandos produziu ACK e dados XML.
- **CONFIRMADO POR FIXTURE:** os streams reais foram preservados; o frame de medição tem header de 32 bytes, XML de 8.195 bytes e CRC recebido `1054`, validado offline.
- **CONFIRMADO POR FIXTURE:** a medição ID 3 possui os cinco ângulos e 15 valores Lab.
- **PENDENTE DE VALIDAÇÃO:** se a resposta foi provocada pelo envio a `.1` ou pelo fallback unicast anterior a `.13`.

## Driver modular do Gate 1

- **CONFIRMADO POR FIXTURE:** o novo `build_discovery_query` reproduz os 22 bytes da captura para a mesma porta local.
- **CONFIRMADO POR FIXTURE:** o novo request de `GetInstrumentInfo` é byte a byte igual ao stream transmitido capturado.
- **CONFIRMADO POR FIXTURE:** CRC, ACK, header, XML e parser de informação reproduzem a semântica da golden.
- **CONFIRMADO POR TESTE:** `BufferedFrameReader` mantém bytes excedentes de frames coalescidos e os entrega na leitura seguinte.
- **CONFIRMADO EM BANCADA:** discovery dirigido ao broadcast calculado `192.168.1.255` recebeu `BYKINSTRUMENT` de `192.168.1.13:6002`; o IP de origem conectou em TCP 6000.
- **CONFIRMADO EM BANCADA:** AUTO e MANUAL retornaram modelo `MicroTriColor`, serial `1327634` e firmware `1.2.0.24448`.
- **CONFIRMADO EM BANCADA:** 20 ciclos AUTO consecutivos de discovery → TCP → `GetInstrumentInfo` → disconnect passaram sem heartbeat ativo ao final.
- **COMPATIBILITY TIMING:** 200 ms entre header/corpo e 700 ms após TCP permanecem centralizados e configurados como comportamento empírico, não especificação oficial.
- **DÍVIDA TÉCNICA:** a resposta de dados continua delimitada por `</CommandResult>` porque as fixtures não comprovam um campo de comprimento utilizável. A decisão agora está isolada no framing.

## Comandos de medição no Gate 2

- **CONFIRMADO POR FIXTURE:** `RetrieveMeasurementIdList`, ID 143, request byte-identical à captura; resposta real lista elementos `Guid` com `Id`, `Name` e `Value`.
- **CONFIRMADO POR FIXTURE:** `RetrieveMeasurement`, ID 42, usa `ParameterInt32 Name="JobListRecordId"`; request do ID 3 é byte-identical à captura.
- **CONFIRMADO POR FIXTURE:** `MeasureValue` fornece ID, nome, GUID, `TimeStamp` e `SerialNumber`; a coleção `LAB` fornece `L*`, `a*`, `b*` por ângulo.
- **CONFIRMADO EM BANCADA:** IDs 1, 2 e 3 foram listados e recuperados consecutivamente na mesma conexão; todos produziram medições válidas.
- **CONFIRMADO EM BANCADA:** 20 ciclos consecutivos AUTO → list → retrieve ID 3 → disconnect passaram com timeout de discovery 1,5 s.
- **OBSERVADO EM BANCADA:** uma tentativa com timeout artificial de 0,8 s falhou no terceiro discovery; o default de produção permanece 3 s.

O parser aceita namespaces por nome local, preserva duplicatas na listagem e não interpreta espectros neste Gate. Resposta `Result != OK` ou ausência de `MeasureValue` vira `MeasurementNotFoundError`.

## Observações reais do Gate 3

- **CONFIRMADO EM BANCADA:** IDs novos 6, 8 e 9 foram detectados por diferença em relação a snapshots e recuperados como medições completas, com GUIDs distintos.
- **CONFIRMADO EM BANCADA:** o ID 7 apareceu em `RetrieveMeasurementIdList` antes de estar recuperável como `Measurement` completa. Durante a mesma espera ele foi rejeitado e não consultado em loop; uma leitura posterior, ID 8, foi aceita.
- **CONFIRMADO EM BANCADA:** após a janela operacional, listagem e recuperação read-only confirmaram IDs 1–9 válidos. Isso caracteriza consistência eventual entre publicação na lista e disponibilidade do conteúdo, sem estabelecer duração fixa.
- **POLÍTICA DO DRIVER/APLICAÇÃO:** identidade nova precisa persistir por dois polls antes de uma única tentativa de retrieve. Se ainda estiver inválida, a espera continua por outro candidato até timeout. Não se infere que todo espectrofotômetro use IDs monotônicos; a ordenação por ID é política baseada no BYK observado.
