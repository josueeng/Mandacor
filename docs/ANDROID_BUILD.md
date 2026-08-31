# Build Android interno

Identidade estável:

- package: `br.com.jftintas.mandacor`
- app version: `1.1.0`
- Android versionCode: `4`

## Validação e execução de desenvolvimento

```bash
cd mobile
npm ci
npm run typecheck
npm test -- --runInBand
npx expo-doctor
npm run validate
```

O projeto nativo está em `mobile/android`. Para executar com toolchain Android configurado:

```bash
cd mobile
npm run android
```

## Builds EAS

`eas.json` oferece:

- `development`: development client interno;
- `preview`: APK para distribuição interna;
- `production`: Android App Bundle.

```bash
cd mobile
npx eas build --platform android --profile preview
```

## Build local e bloqueio atual

Com JDK que contenha compilador e Android SDK configurado:

```bash
cd mobile/android
./gradlew assembleRelease
```

Na validação do Gate P4, a máquina possuía OpenJDK Runtime 25.0.4, mas não `javac`. O Gradle recusou a toolchain por ausência de `JAVA_COMPILER`; portanto nenhum APK foi declarado como gerado. Instalar um JDK compatível (preferencialmente 17 ou 21 conforme a matriz do Android Gradle Plugin), definir `JAVA_HOME` e repetir `assembleRelease` ou usar o profile EAS `preview`.

## Instalação e rollback

Após gerar o APK:

```bash
adb install -r CAMINHO_DO_APK
```

Antes de atualizar, registre versão, URL do backend e IDs ativos. Não limpe dados do app se houver operação ou pending adjustment. Para rollback, reinstale o APK interno anterior com a mesma assinatura e confirme a reconciliação com o backend antes de qualquer ação física.

