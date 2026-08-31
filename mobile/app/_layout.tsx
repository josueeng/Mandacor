import { useFonts } from 'expo-font';
import { DarkTheme, ErrorBoundaryProps, router, Stack, ThemeProvider } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { PropsWithChildren, useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import 'react-native-reanimated';

import { AppProvider } from '@/src/state/AppContext';
import { useMandacor } from '@/src/state/AppContext';
import { ActionButton } from '@/src/components/ui';
import { colors, radius, spacing } from '@/src/theme/tokens';
import { ERROR_BOUNDARY_COPY, errorRecoveryCode } from '@/src/features/startup/model';

export function ErrorBoundary({ error, retry }: ErrorBoundaryProps) {
  return (
    <View style={styles.errorScreen}>
      <Text style={styles.brand}>MANDACOR</Text>
      <Text style={styles.errorTitle}>{ERROR_BOUNDARY_COPY.title}</Text>
      <Text style={styles.detail}>Nenhum dado foi inventado. Tente recarregar esta tela ou volte ao início.</Text>
      <Text style={styles.code}>Código técnico: {errorRecoveryCode(error)}</Text>
      <ActionButton label={ERROR_BOUNDARY_COPY.retry} onPress={retry} />
      <ActionButton label={ERROR_BOUNDARY_COPY.home} secondary onPress={() => router.replace('/')} />
    </View>
  );
}

export const unstable_settings = {
  // Ensure that reloading on `/modal` keeps a back button present.
  initialRouteName: '(tabs)',
};

// Prevent the splash screen from auto-hiding before asset loading is complete.
SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  const [loaded, error] = useFonts({
    SpaceMono: require('../assets/fonts/SpaceMono-Regular.ttf'),
  });

  // Expo Router uses Error Boundaries to catch errors in the navigation tree.
  useEffect(() => {
    if (error) throw error;
  }, [error]);

  useEffect(() => {
    if (loaded) {
      SplashScreen.hideAsync();
    }
  }, [loaded]);

  if (!loaded) {
    return null;
  }

  return <RootLayoutNav />;
}

function RootLayoutNav() {
  return (
    <AppProvider>
      <StartupGate>
        <ThemeProvider value={DarkTheme}>
          <Stack screenOptions={{ headerShown: false }}>
            <Stack.Screen name="(tabs)" />
            <Stack.Screen name="adjustment" />
          </Stack>
        </ThemeProvider>
      </StartupGate>
    </AppProvider>
  );
}

function StartupGate({ children }: PropsWithChildren) {
  const state = useMandacor();
  const [canBypass, setCanBypass] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setCanBypass(true), 5000);
    return () => clearTimeout(timer);
  }, []);
  if (state.hydrated) return children;
  return (
    <View style={styles.startup}>
      <Text style={styles.brand}>MANDACOR</Text>
      <Text style={styles.startupTitle}>Inicializando...</Text>
      <View style={styles.statusCard}>
        <Text style={styles.label}>API</Text>
        <Text style={styles.value}>{state.startupPhase === 'API' ? 'VERIFICANDO' : state.apiState}</Text>
        <Text style={styles.label}>Espectrofotômetro</Text>
        <Text style={styles.value}>{state.startupPhase === 'INSTRUMENT' ? 'VERIFICANDO' : state.instrumentState}</Text>
        <Text style={styles.label}>Sessão</Text>
        <Text style={styles.value}>{['SESSION', 'OPERATION', 'PENDING'].includes(state.startupPhase) ? 'RECUPERANDO' : 'AGUARDANDO'}</Text>
      </View>
      <Text style={styles.detail}>{state.startupDetail}</Text>
      {state.apiState === 'OFFLINE' && <Text style={styles.offline}>MANDACOR SERVER OFFLINE</Text>}
      {canBypass && <ActionButton label="ENTRAR MESMO ASSIM" secondary onPress={state.enterAnyway} />}
    </View>
  );
}

const styles = StyleSheet.create({
  startup: { backgroundColor: colors.background, flex: 1, gap: spacing.lg, justifyContent: 'center', padding: spacing.lg },
  brand: { color: colors.textPrimary, fontSize: 34, fontWeight: '900', letterSpacing: 4 },
  startupTitle: { color: colors.textSecondary, fontSize: 22 },
  statusCard: { backgroundColor: colors.surface, borderColor: colors.border, borderRadius: radius.md, borderWidth: 1, gap: spacing.sm, padding: spacing.md },
  label: { color: colors.textSecondary, fontSize: 14, fontWeight: '800' },
  value: { color: colors.technical, fontFamily: 'SpaceMono', fontSize: 18 },
  detail: { color: colors.textSecondary, fontSize: 16, lineHeight: 24 },
  offline: { color: colors.warning, fontSize: 19, fontWeight: '900' },
  errorScreen: { backgroundColor: colors.background, flex: 1, gap: spacing.lg, justifyContent: 'center', padding: spacing.lg },
  errorTitle: { color: colors.danger, fontSize: 24, fontWeight: '900' },
  code: { color: colors.technical, fontFamily: 'SpaceMono', fontSize: 14 },
});
