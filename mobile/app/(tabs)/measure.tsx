import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Alert, BackHandler, Modal, Pressable, StyleSheet, Text, View } from 'react-native';

import {
  ActionButton,
  Card,
  EmptyState,
  ErrorNotice,
  LabCards,
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

const ACTIVE = new Set(['PREPARED', 'WAITING']);

export default function MeasureScreen() {
  const state = useMandacor();
  const session = state.currentSession;
  const operation = state.activeOperation?.session_id === session?.session_id ? state.activeOperation : null;
  const operationActive = operation ? ACTIVE.has(operation.status) : false;
  const [replaceCandidate, setReplaceCandidate] = useState<'target' | 'sample' | null>(null);

  useEffect(() => {
    if (!operationActive) return;
    const subscription = BackHandler.addEventListener('hardwareBackPress', () => {
      Alert.alert('Cancelar espera?', 'A captura está ativa. Sair silenciosamente poderia ocultar seu estado.', [
        { text: 'CONTINUAR ESPERANDO', style: 'cancel' },
        { text: 'CANCELAR ESPERA', style: 'destructive', onPress: () => void state.cancelCapture() },
      ]);
      return true;
    });
    return () => subscription.remove();
  }, [operationActive, state]);

  if (!session) {
    return (
      <Screen>
        <ScreenHeader eyebrow="MEDIÇÃO" title="Comparação" subtitle="Crie uma sessão para iniciar a captura colorimétrica." />
        <EmptyState>Crie uma nova comparação na tela inicial.</EmptyState>
        <ActionButton label="IR PARA INÍCIO" onPress={() => router.push('/')} secondary />
      </Screen>
    );
  }

  const confirmReplace = (type: 'target' | 'sample') => {
    const measurement = type === 'target' ? session.target : session.sample;
    if (!measurement || operationActive) return;
    setReplaceCandidate(type);
  };

  const candidateMeasurement = replaceCandidate === 'target' ? session.target : session.sample;
  const candidateLabel = replaceCandidate === 'target' ? 'cor alvo' : 'tinta/amostra';

  const replaceConfirmed = () => {
    if (!replaceCandidate) return;
    const type = replaceCandidate;
    setReplaceCandidate(null);
    void state.prepareCapture(type);
  };

  return (
    <Screen>
      <Modal
        animationType="fade"
        onRequestClose={() => setReplaceCandidate(null)}
        transparent
        visible={replaceCandidate !== null}
      >
        <View style={styles.modalBackdrop}>
          <View accessibilityRole="alert" style={styles.modalCard}>
            <Text style={styles.modalEyebrow}>SUBSTITUIR LEITURA</Text>
            <Text style={styles.modalTitle}>Trocar {candidateLabel}?</Text>
            <Text style={styles.modalText}>
              A leitura #{candidateMeasurement?.measurement_id ?? '—'} será substituída somente depois que uma nova medição for feita no espectrofotômetro.
            </Text>
            <View style={styles.modalWarning}>
              <Text style={styles.modalWarningText}>Após confirmar, faça a nova leitura no aparelho. Leituras anteriores não serão usadas automaticamente.</Text>
            </View>
            <ActionButton
              label="PREPARAR NOVA LEITURA"
              onPress={replaceConfirmed}
              disabled={state.busy}
            />
            <ActionButton
              label="CANCELAR"
              onPress={() => setReplaceCandidate(null)}
              disabled={state.busy}
              secondary
            />
          </View>
        </View>
      </Modal>
      <ScreenHeader
        eyebrow="MEDIÇÃO"
        title="Comparação"
        subtitle="Capture primeiro a referência e depois a tinta preparada."
      />
      <View style={styles.samples}>
        <SamplePreview step="1" label="Cor alvo" detail={session.target ? `Leitura #${session.target.measurement_id}` : 'Aguardando'} ready={Boolean(session.target)} onPress={session.target ? () => confirmReplace('target') : undefined} disabled={state.busy || operationActive} />
        <View style={styles.arrow}><Text style={styles.arrowText}>→</Text></View>
        <SamplePreview step="2" label="Tinta / amostra" detail={session.sample ? `Leitura #${session.sample.measurement_id}` : 'Aguardando'} ready={Boolean(session.sample)} onPress={session.sample ? () => confirmReplace('sample') : undefined} disabled={state.busy || operationActive} />
      </View>
      <View style={styles.sessionBar}>
        <Text style={styles.session}>SESSÃO {session.session_id.slice(0, 8)}…</Text>
        <Text style={styles.sessionState}>{presentState(session.state)}</Text>
      </View>
      <ErrorNotice message={state.errorMessage} />

      {session.target && (
        <Card tone="success">
          <SectionHeader>ALVO PROTEGIDO</SectionHeader>
          <TechnicalRow label="Measurement" value={`#${session.target.measurement_id}`} />
        </Card>
      )}

      {operation && (
        <Card tone={operationActive ? 'warning' : operation.status === 'COMPLETED' ? 'success' : 'default'}>
          <SectionHeader>CAPTURA EM ANDAMENTO</SectionHeader>
          <StatusBadge online={operation.status === 'COMPLETED'} label={presentState(operation.status)} />
          <TechnicalRow label="Operação" value={`${operation.operation_id.slice(0, 8)}…`} />
          {operationActive && (
            <View style={styles.waiting}>
              <Text style={styles.waitTitle}>ESPERANDO NOVA MEDIÇÃO</Text>
              <Text style={styles.instruction}>
                AGORA faça uma leitura da {operation.type === 'TARGET' ? 'COR ALVO' : 'TINTA'} no espectrofotômetro.
              </Text>
              <Text style={styles.angles}>15°  ·  25°  ·  45°  ·  75°  ·  105°</Text>
              <ActionButton label="CANCELAR ESPERA" onPress={() => void state.cancelCapture()} disabled={state.busy} warning />
            </View>
          )}
          {operation.status === 'TIMED_OUT' && (
            <>
              <Text style={styles.warning}>Nenhuma nova leitura foi detectada.</Text>
              <ActionButton
                label="TENTAR NOVAMENTE"
                onPress={() => void state.prepareCapture(operation.type === 'TARGET' ? 'target' : 'sample')}
                disabled={state.busy}
              />
            </>
          )}
        </Card>
      )}

      {!session.target && !operationActive && operation?.status !== 'TIMED_OUT' && (
        <>
          <Card tone="info">
            <SectionHeader>COR ALVO</SectionHeader>
            <Text style={uiStyles.muted}>PRONTO PARA MEDIR. O aviso de leitura só aparecerá após o snapshot do backend.</Text>
          </Card>
          <ActionButton label="PREPARAR LEITURA DO ALVO" onPress={() => void state.prepareCapture('target')} disabled={state.busy} />
        </>
      )}

      {session.target && (
        <>
          <SectionHeader>COR ALVO CAPTURADA · #{session.target.measurement_id}</SectionHeader>
          <LabCards angles={session.target.angles} />
        </>
      )}

      {session.target && !session.sample && !operationActive && operation?.status !== 'TIMED_OUT' && (
        <ActionButton label="PREPARAR LEITURA DA TINTA" onPress={() => void state.prepareCapture('sample')} disabled={state.busy} />
      )}

      {session.sample && (
        <>
          <SectionHeader>AMOSTRA CAPTURADA · #{session.sample.measurement_id}</SectionHeader>
          <LabCards angles={session.sample.angles} />
        </>
      )}

      {session.state === 'READY_FOR_COMPARISON' && (
        <ActionButton label="VER RESULTADO" onPress={() => router.push('/results')} />
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  modalBackdrop: {
    alignItems: 'center',
    backgroundColor: 'rgba(0, 0, 0, 0.78)',
    flex: 1,
    justifyContent: 'center',
    padding: spacing.md,
  },
  modalCard: {
    backgroundColor: colors.surface,
    borderColor: colors.borderStrong,
    borderRadius: 16,
    borderWidth: 1,
    gap: spacing.mdSm,
    maxWidth: 420,
    padding: spacing.lg,
    width: '100%',
  },
  modalEyebrow: { color: colors.technical, fontSize: 10, fontWeight: '900', letterSpacing: 1.2 },
  modalTitle: { color: colors.textPrimary, fontSize: 22, fontWeight: '900' },
  modalText: { color: colors.textSecondary, fontSize: 14, lineHeight: 21 },
  modalWarning: { backgroundColor: colors.warningSoft, borderRadius: 9, padding: spacing.mdSm },
  modalWarningText: { color: colors.warning, fontSize: 12, fontWeight: '800', lineHeight: 18 },
  samples: { alignItems: 'center', flexDirection: 'row', gap: 8 },
  sampleCard: { backgroundColor: colors.surface, borderColor: colors.border, borderRadius: 14, borderWidth: 1, flex: 1, gap: 7, padding: 10 },
  sampleCardReady: { borderColor: colors.success },
  sampleTop: { alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between' },
  step: { alignItems: 'center', backgroundColor: colors.surfaceElevated, borderRadius: 10, height: 20, justifyContent: 'center', width: 20 },
  stepText: { color: colors.textSecondary, fontSize: 10, fontWeight: '900' },
  readyText: { color: colors.success, fontSize: 9, fontWeight: '900' },
  replaceHint: { color: colors.technical, fontSize: 9, fontWeight: '900', marginTop: 2 },
  swatch: { backgroundColor: '#7E8995', borderRadius: 8, height: 64, width: '100%' },
  swatchPending: { backgroundColor: colors.surfaceElevated },
  sampleLabel: { color: colors.textPrimary, fontSize: 12, fontWeight: '900' },
  sampleDetail: { color: colors.textSecondary, fontSize: 10 },
  arrow: { alignItems: 'center', backgroundColor: colors.technicalSoft, borderRadius: 20, height: 34, justifyContent: 'center', width: 34 },
  arrowText: { color: colors.technical, fontSize: 18, fontWeight: '900' },
  sessionBar: { alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between' },
  session: { color: colors.textMuted, fontFamily: 'SpaceMono', fontSize: 9 },
  sessionState: { color: colors.technical, fontSize: 10, fontWeight: '900' },
  waiting: { gap: 10, marginTop: 4 },
  waitTitle: { color: colors.warning, fontSize: 14, fontWeight: '900', textAlign: 'center' },
  instruction: { color: colors.textPrimary, fontSize: 15, fontWeight: '800', lineHeight: 21, textAlign: 'center' },
  angles: { color: colors.technical, fontFamily: 'SpaceMono', fontSize: 12, textAlign: 'center' },
  warning: { color: colors.warning, fontSize: 13, fontWeight: '800' },
});

function SamplePreview({
  step,
  label,
  detail,
  ready,
  onPress,
  disabled,
}: {
  step: string;
  label: string;
  detail: string;
  ready: boolean;
  onPress?: () => void;
  disabled?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole={onPress ? 'button' : undefined}
      accessibilityLabel={onPress ? `Trocar ${label} pela última leitura do espectrofotômetro` : label}
      disabled={disabled || !onPress}
      onPress={onPress}
      style={({ pressed }) => [
        styles.sampleCard,
        ready && styles.sampleCardReady,
        pressed && { opacity: 0.72 },
      ]}
    >
      <View style={styles.sampleTop}>
        <View style={styles.step}><Text style={styles.stepText}>{step}</Text></View>
        <Text style={styles.readyText}>{ready ? 'CONCLUÍDO' : 'PENDENTE'}</Text>
      </View>
      <View style={[styles.swatch, !ready && styles.swatchPending]} />
      <Text style={styles.sampleLabel}>{label}</Text>
      <Text style={styles.sampleDetail}>{detail}</Text>
      {ready && <Text style={styles.replaceHint}>TOQUE PARA TROCAR</Text>}
    </Pressable>
  );
}
