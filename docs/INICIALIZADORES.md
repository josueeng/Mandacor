# Inicializadores MANDACOR

Os inicializadores levantam a API na porta `8000`, detectam o IP da rede local, configuram o aplicativo para usar `http://IP_LOCAL:8000` e iniciam o Expo em modo LAN. O QR Code permanece visível no terminal.

As origens do Expo em `localhost`, `127.0.0.1` e no IP LAN detectado são liberadas explicitamente no CORS do backend. O wildcard `*` não é usado.

Ao abrir o aplicativo por esse QR Code, a URL detectada substitui uma URL antiga que tenha ficado salva no celular. Isso evita que o Expo aponte para uma porta ou computador usado anteriormente.

## Pré-requisitos

- Python 3.11 ou superior;
- Node.js LTS com npm;
- computador e celular conectados à mesma rede local;
- Expo Go instalado no celular.

Na primeira execução, o inicializador cria `.venv` no Linux ou `.venv-windows` no Windows quando necessário e instala as dependências Python e Node. Portanto, a primeira abertura pode precisar de internet e demorar alguns minutos.

## Windows

Dê dois cliques em `INICIAR_MANDACOR_WINDOWS.bat`. O backend abre em uma segunda janela e o QR Code aparece na janela principal. Ao terminar, feche as duas janelas.

Se o Firewall do Windows solicitar autorização, permita o acesso do Python e do Node.js somente em redes privadas. Caso a detecção escolha a interface errada, abra o Prompt de Comando na pasta do projeto e execute:

```bat
set MANDACOR_LAN_IP=192.168.1.11
INICIAR_MANDACOR_WINDOWS.bat
```

## Linux

O arquivo já deve estar marcado como executável. Dê dois cliques em `INICIAR_MANDACOR_LINUX.desktop` e escolha **Confiar e iniciar** se o ambiente gráfico perguntar. O atalho `.desktop` foi preparado para a pasta atual; se o projeto for movido, use o `.sh`, que localiza a pasta automaticamente:

```bash
./INICIAR_MANDACOR_LINUX.sh
```

Ao pressionar `Ctrl+C`, o Expo e o backend iniciado pelo script são encerrados. O log do backend fica em `logs/backend.log`. Para informar manualmente o IP LAN:

```bash
MANDACOR_LAN_IP=192.168.1.11 ./INICIAR_MANDACOR_LINUX.sh
```

As portas padrão são `8000` para o backend e `8081` para o Expo. Para uma execução alternativa no Linux, use `MANDACOR_BACKEND_PORT` e `MANDACOR_EXPO_PORT`; no Windows, defina as mesmas variáveis com `set` antes de abrir o `.bat`.

## QR Code não conecta

1. Confirme que celular e computador estão na mesma rede Wi-Fi/LAN.
2. Desative temporariamente VPNs que alterem a rota local.
3. Libere as portas `8000` e `8081` no firewall da rede privada.
4. Confira se o endereço mostrado em `API do celular` abre no navegador do celular acrescentando `/health`.
5. Se houver várias placas de rede, defina `MANDACOR_LAN_IP` manualmente conforme os exemplos acima.

## Uso diário na loja

Para que a API inicie sozinha com o computador, sem abrir o inicializador, instale-a como serviço com `INSTALAR_SERVICO_WINDOWS.bat` (Windows) ou `INSTALAR_SERVICO_LINUX.sh` (Linux). O passo a passo completo, incluindo o app instalado como APK e o acesso fora da loja, está em `docs/IMPLANTACAO_LOJA.md`.
