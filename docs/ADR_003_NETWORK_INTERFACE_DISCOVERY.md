# ADR 003 — Descoberta de interfaces de rede

- Status: aceita para Gate 1
- Data: 2026-08-29

## Contexto

AUTO precisa calcular broadcast usando endereço e máscara reais, ignorar interfaces inadequadas e operar sem IP de rede hardcoded. A biblioteca padrão oferece `ipaddress`, mas não uma API portável completa para endereços/máscaras de todas as interfaces.

## Decisão

No ambiente Linux de bancada, usar somente biblioteca padrão:

- `socket.if_nameindex()` para nomes;
- `fcntl.ioctl` para flags, IPv4 e netmask;
- `ipaddress.IPv4Network(..., strict=False)` para broadcast;
- `select.select` para coletar respostas em vários sockets;
- um socket ligado ao IPv4 local de cada interface selecionada.

Interfaces down, loopback e prefixos virtuais conhecidos (`docker`, `br-`, `veth`, `virbr`) são ignorados no AUTO, salvo evolução futura. `local_interface` explícita restringe por nome ou IPv4. `discovery_address` explícito e MANUAL sem interface local usam bind genérico e não dependem de enumeração.

Nenhuma dependência externa foi adicionada.

## Evidência

Na bancada, a enumeração selecionou `wlx78bdbc4c8ed5`, IPv4 `192.168.1.11`, netmask `255.255.255.0`, broadcast calculado `192.168.1.255`. O BYK respondeu de `192.168.1.13:6002` e aceitou TCP no mesmo IP.

Testes unitários confirmam cálculo com `/24`, `/23` e `/16`; não existe concatenação manual de `.255`.

## Consequências e limitações

- AUTO por enumeração é atualmente Linux/POSIX; Windows exigirá outro provider ou uma dependência pequena em gate futuro.
- Configuração MANUAL e `discovery_address` explícito continuam disponíveis sem essa enumeração quando `local_interface` não é exigida.
- A heurística de interfaces é deliberadamente simples e injetável, permitindo melhorar tratamento de VPN/VLAN sem mudar o protocolo BYK.
- A descoberta coleta uma lista e deduplica endpoint; não escolhe silenciosamente entre múltiplos instrumentos.

