# Mobile MANDACOR

O app mobile é uma interface React Native/Expo que consome exclusivamente a API local do Gate P1. O backend permanece fonte da verdade para instrumento, sessão, captura e todos os resultados colorimétricos.

## Stack

- Expo SDK 57.0.0 (`expo` 57.0.18)
- React Native 0.86.3
- React 19.2.3
- TypeScript 6.0.3 em modo strict
- Expo Router 57.0.17, com cinco abas: Início, Medir, Resultado, Histórico e Config
- AsyncStorage 2.2.0 para URL, session ID e operation ID
- `fetch` encapsulado por `MandacorApiClient`

## Backend na rede local

No computador:

```bash
.venv/bin/python -m mandacor api serve --host 0.0.0.0 --port 8000
```

O bind `0.0.0.0` expõe a API na LAN e deve ser usado somente em rede confiável. Descubra o IP LAN do computador e configure, por exemplo:

```text
http://192.168.1.11:8000
```

`127.0.0.1` no celular aponta para o próprio celular, não para o computador. O IP acima é somente exemplo e não está hardcoded.

## Configuração do app

Copie opcionalmente o exemplo de ambiente e ajuste o endereço:

```bash
cd mobile
cp .env.example .env.local
```

```dotenv
EXPO_PUBLIC_MANDACOR_API_URL=http://IP_DO_COMPUTADOR:8000
EXPO_PUBLIC_ELONGATION_TOLERANCE=2.00
```

A URL também pode ser testada e persistida na Central de Conexão. `TESTAR E SALVAR` exige health compatível e consulta o estado do instrumento antes de substituir a configuração. Nenhum segredo é armazenado.

`EXPO_PUBLIC_ELONGATION_TOLERANCE` define o limite operacional da abertura da curva de ΔL* entre os cinco ângulos. O padrão é `2.00`. O app mostra `PASSA NO ALONGAMENTO` quando `max(ΔL*) - min(ΔL*)` não ultrapassa esse valor. Um deslocamento uniforme de luminosidade não altera o alongamento; a aprovação de cor continua sendo uma análise separada.

## Execução

```bash
cd mobile
npm install
npx expo start
```

Pressione `a` para abrir no emulador/dispositivo Android, ou leia o QR code com Expo Go. Para um emulador Android, `10.0.2.2` normalmente representa o host:

```bash
EXPO_PUBLIC_MANDACOR_API_URL=http://10.0.2.2:8000 npx expo start --android
```

O manifesto de build usa `expo-build-properties` com `usesCleartextTraffic: true` exclusivamente porque o MVP acessa uma API HTTP na LAN. Não há relaxamento adicional de segurança nem endpoint cloud.

## Fluxo

1. Startup testa `/health`; somente com API online consulta `/instrument/status`.
2. O operador conecta em modo AUTO ou informa o IP manual. Múltiplos candidatos são apresentados sem seleção automática.
3. `NOVA COMPARAÇÃO` cria uma única ColorSession no backend.
4. `PREPARAR LEITURA DO ALVO` recebe o operation ID antes de instruir a leitura física.
5. O app chama `/wait` e acompanha `/operations/{id}` a cada 750 ms, com cancelamento e timeout sem progresso fictício.
6. Após TARGET, o mesmo fluxo captura SAMPLE preservando o alvo.
7. Somente em `READY_FOR_COMPARISON`, o app consulta comparison, diagnosis e correction needs.
8. O operador informa sistema/acabamento para consultar pigment candidates. O app nunca infere contexto nem mostra dosagem.

URL, session ID e operation ID são persistidos no app. Na reabertura, o app consulta a API antes de restaurar estado; somente um 404 explícito descarta um ID. Desde o P4, sessões do backend também sobrevivem ao restart em JSON versionado; operações em voo são reconciliadas pelo estado persistido da sessão, enquanto tasks de espera são recriadas de modo controlado.

## Erros e estados

`MandacorApiClient` aplica timeout, parsing JSON e o envelope `error.code/message/details`. O mapping PT-BR é centralizado e preserva o código original. API offline e instrumento desconectado são mostrados separadamente. Mutations desabilitam ações concorrentes para impedir duplo connect, create ou prepare.

## Design

O tema usa fundo preto/grafite, texto branco, dados técnicos azuis, ações vermelhas e verde/âmbar somente para status. Botões têm altura mínima de 54 px e status usa texto mais indicador visual. Os cinco ângulos são ordenados explicitamente como 15°, 25°, 45°, 75° e 105°.

## Validação

```bash
cd mobile
npm run typecheck
npm test
npx expo-doctor
npm run validate
```

`validate` gera um bundle Android em `mobile/dist/android`, ignorado pelo Git. Não existem mocks no runtime. O fluxo integral foi exercitado no Pixel 7/Expo Go contra uma factory FastAPI P1 com fake instrument somente durante o teste; a execução normal sempre usa a URL configurada.

O mobile não contém protocolo BYK, discovery UDP, TCP, CRC, XML, heartbeat, cálculo Lab/ΔE, diagnóstico, regra de pigmento ou cálculo de gramas. Ele deriva apenas a indicação operacional de alongamento a partir dos ΔL* entregues pela API.

## Workflow de ajuste — Gate P3

Uma comparação `READY_FOR_COMPARISON` habilita `NOVO AJUSTE`. O operador informa sistema, acabamento, volume real, um ou mais pigmentos/massas e motivo. Vírgula decimal é normalizada apenas para transporte; presets 450/900/3600 ml não calculam quantidade. Review e confirmação física são etapas distintas.

Depois de `confirm-applied`, todos os campos ficam somente leitura e o app mostra `NÃO ADICIONE O PIGMENTO NOVAMENTE.`. A captura AFTER reutiliza operations/snapshot/polling do P2. Timeout preserva o pending; retry usa o mesmo adjustment ID e não envia novamente massas ou confirmação. Se a resposta do `confirm-applied` for ambígua, o app consulta o status e exige verificação em vez de repetir a mutation.

O pending adjustment ID é persistido. No startup, o app consulta primeiro o ID e depois o endpoint global de pending; a Home apresenta o card de retomada antes das demais ações. Abandono após aplicação exige motivo e não apaga o registro. A aba Histórico lista a cadeia TARGET → BEFORE → AFTER e abre detalhes. Response, errors vs target, outcomes e worst angles vêm prontos da API; o mobile apenas formata esses dados.

## Production readiness — Gate P4

O startup agora explicita as fases CONFIG → API → INSTRUMENT → SESSION → OPERATION → PENDING → READY. API e BYK usam estados `ONLINE`, `OFFLINE` e `UNKNOWN`; API offline implica BYK desconhecido, não desconectado. Todas as requisições têm timeout com fallback lógico, e o contrato exige `api_version: v1`.

A Central de Conexão testa o endereço antes de persistir e exibe host, versões, latência, última verificação, instrumento, IDs recuperados e código técnico. Sessão, captura ativa e pending são reconciliados com o backend; somente 404 explícito remove referência local. Em background, polling é encerrado e, no retorno, o estado remoto é consultado antes de qualquer retomada.

Duplo toque é bloqueado nas ações críticas. Uma resposta ambígua de `confirm-applied` nunca provoca reenvio automático: o app consulta o ajuste e mantém o aviso contra reaplicação. Um error boundary oferece tentar novamente ou voltar ao início sem apresentar stack trace.

Package Android: `br.com.jftintas.mandacor`, versão `1.1.0`, versionCode `4`. Builds e o bloqueio local do APK estão em `ANDROID_BUILD.md`.
