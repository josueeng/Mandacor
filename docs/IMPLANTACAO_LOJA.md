# Implantação em uma loja (custo zero)

## Por que o servidor fica na loja

O backend fala com o BYK pela rede local: descoberta por broadcast UDP (porta 6002) e conexão TCP (porta 6000). Um servidor em nuvem não alcança o instrumento dentro da loja. Por isso a API roda num computador na mesma rede do BYK, e o celular se conecta a esse computador.

```text
Celular (app MANDACOR) ──Wi‑Fi da loja──> PC da bancada (API :8000) ──rede local──> BYK
        └──(opcional, fora da loja)── Tailscale ──┘
```

## 1. Preparar o PC da bancada

- Mantenha o PC ligado durante o expediente, conectado à mesma rede do BYK.
- Reserve um IP fixo para o PC no roteador (opção "reserva de DHCP" / "IP fixo por MAC"). Sem isso o endereço pode mudar e o app perde o servidor.
- Desative a suspensão automática do PC.

## 2. Instalar a API como serviço (Linux)

```bash
./INSTALAR_SERVICO_LINUX.sh
```

O script cria o ambiente Python se necessário, instala as dependências, registra o serviço `mandacor` no systemd e mostra o endereço para configurar no app. A API passa a iniciar sozinha com o computador e reinicia em caso de falha.

- Ver o log: `journalctl -u mandacor -f`
- Reiniciar: `sudo systemctl restart mandacor`
- Remover: `./INSTALAR_SERVICO_LINUX.sh --remover`

Se o firewall estiver ativo, libere a porta 8000 apenas para a rede local, por exemplo `sudo ufw allow from 192.168.1.0/24 to any port 8000 proto tcp`.

Não use o inicializador `INICIAR_MANDACOR_LINUX.sh` ao mesmo tempo que o serviço: os dois usam a porta 8000.

## 3. Instalar o app no celular (APK)

O plano gratuito do Expo (EAS) gera o APK na nuvem do Expo. É preciso uma conta gratuita em expo.dev.

```bash
cd mobile
npm ci
npx eas login
npx eas build --platform android --profile preview
```

Ao terminar, o EAS mostra um link para baixar o APK. Abra o link no celular e instale (o Android pede para permitir "instalar apps desconhecidos").

No app, abra **CONFIG**, informe o IP do PC e a porta `8000` e salve. O selo de servidor deve ficar **CONECTADO**. Depois conecte o BYK pela tela inicial.

## 4. Acesso fora da loja (opcional)

O Tailscale cria uma rede privada entre o PC e o celular, sem abrir portas no roteador e sem expor a API na internet.

1. Crie uma conta em tailscale.com e instale o Tailscale no PC da bancada e no celular, entrando com a mesma conta.
2. No PC, veja o endereço Tailscale com `tailscale ip -4` (algo como `100.x.y.z`).
3. Fora da loja, troque o servidor do app em **CONFIG** para `100.x.y.z:8000`. Dentro da loja, o IP local continua funcionando.

Confira os termos do plano gratuito do Tailscale para uso comercial antes de adotar.

## Segurança

A API ainda não tem login. Qualquer aparelho na mesma rede pode chamá-la. Por isso:

- não deixe o PC da bancada na rede de visitantes;
- não exponha a porta 8000 no roteador nem em túneis públicos; para acesso remoto use somente a rede privada do Tailscale.

## Backup dos dados

Os registros ficam na pasta `data/` do projeto (`sessions.json`, `pending_adjustment.json`, `adjustments.csv`, `adjustment_components.csv`, `formulas.sqlite3`). Copie essa pasta periodicamente para um pendrive ou um serviço de armazenamento gratuito.

O catálogo `formulas.sqlite3` foi gerado do banco do SkyMix; confirme com o fornecedor se ele pode ser copiado para serviços de terceiros.
