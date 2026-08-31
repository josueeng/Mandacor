import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, StyleSheet, Text, View } from 'react-native';

import {
  ActionButton,
  Card,
  ErrorNotice,
  Field,
  Screen,
  ScreenHeader,
  SectionHeader,
  StatusBadge,
  TechnicalRow,
  uiStyles,
} from '@/src/components/ui';
import { presentState } from '@/src/presentation/format';
import { useMandacor } from '@/src/state/AppContext';
import { colors, spacing } from '@/src/theme/tokens';

export default function HomeScreen() {
  const state = useMandacor();
  const [manualHost, setManualHost] = useState('');

  const newComparison = async () => {
    if (state.currentSession?.state === 'READY_FOR_COMPARISON') {
      Alert.alert(
        'Iniciar nova sessão?',
        `A sessão ${state.currentSession.session_id.slice(0, 8)}… continuará preservada no backend.`,
        [
          { text: 'CONTINUAR SESSÃO', style: 'cancel', onPress: () => router.push('/measure') },
          { text: 'NOVA SESSÃO', onPress: () => void createAndOpen() },
        ],
      );
      return;
    }
    await createAndOpen();
  };

  const createAndOpen = async () => {
    await state.createComparison();
    router.push('/measure');
  };

  return (
    <Screen>
      <ScreenHeader
        eyebrow="BANCADA DE COR"
        title="MANDACOR"
        subtitle="Medição, comparação e ajuste de cor automotiva em um fluxo seguro."
      />

      <ErrorNotice message={state.errorMessage} />

      {state.pendingAdjustment && (
        <View style={styles.pendingCard}>
          <Text style={styles.pendingTitle}>AJUSTE JÁ APLICADO · AFTER PENDENTE</Text>
          <Text style={styles.pendingWarning}>NÃO ADICIONE O PIGMENTO NOVAMENTE.</Text>
          <TechnicalRow label="Ajuste" value={`${state.pendingAdjustment.adjustment_id.slice(0, 8)}…`} />
          <TechnicalRow label="BEFORE" value={`#${state.pendingAdjustment.before_measurement_id}`} />
          <TechnicalRow label="Componentes" value={state.pendingAdjustment.components.map((item) => `${item.pigment_code} ${item.quantity_g} g`).join(' + ')} />
          <ActionButton label="CONTINUAR LEITURA AFTER" warning onPress={() => router.push(`../adjustment?id=${state.pendingAdjustment!.adjustment_id}`)} />
        </View>
      )}

      <Card tone={state.apiState === 'ONLINE' ? 'success' : 'warning'}>
        <SectionHeader>API LOCAL</SectionHeader>
        <StatusBadge online={state.apiState === 'ONLINE'} label={`SERVIDOR ${presentState(state.apiState)}`} />
        <Text style={uiStyles.muted}>{state.baseUrl}</Text>
        {state.apiState !== 'ONLINE' && <ActionButton label="TESTAR NOVAMENTE" onPress={() => void state.testApi()} disabled={state.busy} secondary />}
      </Card>

      <Card tone={state.instrumentState === 'ONLINE' ? 'success' : 'warning'}>
        <SectionHeader>ESPECTROFOTÔMETRO</SectionHeader>
        <StatusBadge
          online={state.instrumentState === 'ONLINE'}
          label={`BYK ${presentState(state.instrumentState)}`}
        />
        {state.apiState === 'ONLINE' && state.instrumentState === 'ONLINE' && state.instrument.instrument ? (
          <>
            <TechnicalRow label="Modelo" value={state.instrument.instrument.model} />
            <TechnicalRow label="Serial" value={state.instrument.instrument.serial} />
            <TechnicalRow label="Firmware" value={state.instrument.instrument.firmware} />
            <ActionButton label="DESCONECTAR" onPress={() => void state.disconnectInstrument()} disabled={state.busy} secondary />
          </>
        ) : state.apiState === 'ONLINE' ? (
          <>
            <ActionButton
              label="CONECTAR AUTOMATICAMENTE"
              onPress={() => void state.connectInstrument('auto')}
              disabled={state.busy || !state.apiOnline}
            />
            <Field
              accessibilityLabel="IP do espectrofotômetro"
              keyboardType="numbers-and-punctuation"
              placeholder="IP manual, ex.: 192.168.1.13"
              value={manualHost}
              onChangeText={setManualHost}
            />
            <ActionButton
              label="CONECTAR POR IP"
              onPress={() => void state.connectInstrument('manual', manualHost)}
              disabled={state.busy || !state.apiOnline || !manualHost.trim()}
              secondary
            />
          </>
        ) : <Text style={uiStyles.muted}>Estado desconhecido: conecte primeiro ao servidor MANDACOR.</Text>}
        {state.candidates.length > 1 && (
          <View style={styles.candidates}>
            <Text style={styles.warning}>ESCOLHA UM EQUIPAMENTO</Text>
            {state.candidates.map((item) => (
              <ActionButton
                key={`${item.host}-${item.serial ?? 'unknown'}`}
                label={`${item.model ?? 'BYK'} · ${item.serial ?? 'SEM SERIAL'} · ${item.host}`}
                onPress={() => void state.connectInstrument('manual', item.host)}
                disabled={state.busy}
                secondary
              />
            ))}
          </View>
        )}
      </Card>

      <Card tone={state.currentSession ? 'info' : 'default'}>
        <SectionHeader>SESSÃO ATUAL</SectionHeader>
        {state.currentSession ? (
          <>
            <TechnicalRow label="UUID" value={`${state.currentSession.session_id.slice(0, 8)}…`} />
            <TechnicalRow label="Etapa" value={presentState(state.currentSession.state)} />
            <ActionButton label="CONTINUAR SESSÃO" onPress={() => router.push('/measure')} secondary />
          </>
        ) : (
          <Text style={uiStyles.muted}>Nenhuma comparação em andamento.</Text>
        )}
      </Card>

      <ActionButton
        label="NOVA COMPARAÇÃO"
        onPress={() => void newComparison()}
        disabled={state.busy || !state.apiOnline || !state.instrument.connected || Boolean(state.pendingAdjustment)}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  candidates: { gap: spacing.sm },
  warning: { color: colors.warning, fontWeight: '900' },
  pendingCard: { backgroundColor: '#3B1113', borderColor: colors.danger, borderRadius: 14, borderWidth: 2, gap: spacing.sm, padding: spacing.md },
  pendingTitle: { color: colors.textPrimary, fontSize: 19, fontWeight: '900' },
  pendingWarning: { color: colors.danger, fontSize: 21, fontWeight: '900', textAlign: 'center' },
});
