import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Alert, BackHandler, Modal, Pressable, StyleSheet, Text, View } from 'react-native';

import { MandacorApiClient } from '@/src/api/client';
import { friendlyError } from '@/src/api/errors';
import { ActionButton, Callout, Card, ErrorNotice, Field, Screen, ScreenHeader, SectionHeader, TechnicalRow, uiStyles } from '@/src/components/ui';
import {
  APPLIED_WARNING,
  AdjustmentForm,
  buildAdjustmentPayload,
  completedResultData,
  OPERATOR_QUANTITY_NOTICE,
  VOLUME_PRESETS,
} from '@/src/features/adjustments/model';
import {
  assessmentFindings,
  OPERATOR_DISAGREEMENT_NOTICE,
  presentVerdict,
} from '@/src/features/adjustments/assessment';
import { confirmAppliedWithVerification } from '@/src/features/adjustments/workflow';
import { formatSigned, presentState } from '@/src/presentation/format';
import { useMandacor } from '@/src/state/AppContext';
import { colors, radius, spacing } from '@/src/theme/tokens';
import { Adjustment, FinishType, PaintSystem, TrialAssessment } from '@/src/types/api';

const SYSTEMS: PaintSystem[] = ['POLYESTER_BASECOAT', 'PU', 'UNKNOWN'];
const FINISHES: FinishType[] = ['SOLID', 'METALLIC', 'PEARL', 'UNKNOWN'];
const TERMINAL = new Set(['COMPLETED', 'TIMED_OUT', 'CANCELLED', 'FAILED']);

const initialForm: AdjustmentForm = {
  system: 'POLYESTER_BASECOAT',
  finish: 'METALLIC',
  volume: '',
  components: [{ pigmentCode: '', quantity: '' }],
  reason: '',
};

export default function AdjustmentScreen() {
  const params = useLocalSearchParams<{ id?: string }>();
  const app = useMandacor();
  const client = useMemo(() => new MandacorApiClient(app.baseUrl), [app.baseUrl]);
  const [form, setForm] = useState<AdjustmentForm>(initialForm);
  const [reviewing, setReviewing] = useState(false);
  const [adjustment, setAdjustment] = useState<Adjustment | null>(null);
  const [confirmVisible, setConfirmVisible] = useState(false);
  const [abandonVisible, setAbandonVisible] = useState(false);
  const [abandonReason, setAbandonReason] = useState('');
  const [verificationRequired, setVerificationRequired] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [visualResult, setVisualResult] = useState<NonNullable<Adjustment['visual_result']>>('UNKNOWN');
  const [operatorStatus, setOperatorStatus] = useState<NonNullable<Adjustment['operator_status']>>('UNKNOWN');
  const [observations, setObservations] = useState('');
  const criticalAction = useRef<string | null>(null);

  useEffect(() => {
    const formDirty = Boolean(
      form.volume || form.reason || form.components.some((item) => item.pigmentCode || item.quantity),
    );
    if (adjustment || !formDirty) return;
    const subscription = BackHandler.addEventListener('hardwareBackPress', () => {
      Alert.alert('Descartar formulário?', 'Os dados ainda não foram registrados como ajuste.', [
        { text: 'CONTINUAR EDITANDO', style: 'cancel' },
        { text: 'DESCARTAR', style: 'destructive', onPress: () => router.back() },
      ]);
      return true;
    });
    return () => subscription.remove();
  }, [adjustment, form]);

  const loadAdjustment = async (id: string) => {
    try {
      const loaded = await client.getAdjustment(id);
      setAdjustment(loaded);
      if (loaded.visual_result) setVisualResult(loaded.visual_result);
      if (loaded.operator_status) setOperatorStatus(loaded.operator_status);
      setObservations(loaded.observations ?? '');
      if (loaded.lifecycle === 'COMPLETED') await app.refreshPendingAdjustment();
    } catch (caught) {
      setError(friendlyError(caught));
    }
  };

  useEffect(() => {
    const id = params.id ?? app.pendingAdjustment?.adjustment_id;
    if (id) void loadAdjustment(id);
    // The ID is the stable recovery key; the loaded object is refreshed separately below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id, app.pendingAdjustment?.adjustment_id]);

  useEffect(() => {
    const operation = app.activeOperation;
    if (!adjustment || operation?.type !== 'AFTER' || !TERMINAL.has(operation.status)) return;
    void loadAdjustment(adjustment.adjustment_id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [app.activeOperation?.status]);

  const updateComponent = (index: number, field: 'pigmentCode' | 'quantity', value: string) => {
    setForm((current) => ({
      ...current,
      components: current.components.map((item, itemIndex) =>
        itemIndex === index ? { ...item, [field]: value } : item),
    }));
  };

  const goToReview = () => {
    if (!buildAdjustmentPayload(form)) {
      setError('Preencha sistema, acabamento, volume, pigmentos, massas e motivo com valores válidos.');
      return;
    }
    setError(null);
    setReviewing(true);
  };

  const createPlanned = async () => {
    const payload = buildAdjustmentPayload(form);
    if (!payload || !app.currentSession) return;
    if (criticalAction.current) return;
    criticalAction.current = 'create-adjustment';
    setBusy(true);
    try {
      setAdjustment(await client.createAdjustment(app.currentSession.session_id, payload));
      setReviewing(false);
    } catch (caught) {
      setError(friendlyError(caught));
    } finally {
      criticalAction.current = null;
      setBusy(false);
    }
  };

  const confirmApplied = async () => {
    if (!adjustment) return;
    if (criticalAction.current) return;
    criticalAction.current = 'confirm-applied';
    setConfirmVisible(false);
    setBusy(true);
    try {
      const result = await confirmAppliedWithVerification(client, adjustment.adjustment_id);
      setVerificationRequired(result.verificationRequired);
      if (result.adjustment) {
        setAdjustment(result.adjustment);
        await app.refreshPendingAdjustment();
      }
    } catch (caught) {
      setError(friendlyError(caught));
    } finally {
      criticalAction.current = null;
      setBusy(false);
    }
  };

  const verifyStatus = async () => {
    if (!adjustment) return;
    setBusy(true);
    try {
      const latest = await client.getAdjustment(adjustment.adjustment_id);
      setAdjustment(latest);
      setVerificationRequired(latest.lifecycle === 'PLANNED');
      await app.refreshPendingAdjustment();
    } catch (caught) {
      setError(friendlyError(caught));
    } finally {
      setBusy(false);
    }
  };

  const abandon = async () => {
    if (!adjustment || !abandonReason.trim()) return;
    if (criticalAction.current) return;
    criticalAction.current = 'abandon';
    setBusy(true);
    try {
      setAdjustment(await client.abandonAdjustment(adjustment.adjustment_id, abandonReason));
      await app.refreshPendingAdjustment();
      setAbandonVisible(false);
    } catch (caught) {
      setError(friendlyError(caught));
    } finally {
      criticalAction.current = null;
      setBusy(false);
    }
  };

  const submitFeedback = async () => {
    if (!adjustment) return;
    setBusy(true);
    try {
      setAdjustment(await client.submitAdjustmentFeedback(
        adjustment.adjustment_id, visualResult, operatorStatus, observations,
      ));
    } catch (caught) {
      setError(friendlyError(caught));
    } finally {
      setBusy(false);
    }
  };

  if (!adjustment && !app.currentSession) {
    return <Screen><ScreenHeader eyebrow="BANCADA" title="Ajuste de cor" subtitle="Conclua uma comparação antes de registrar um ajuste." /></Screen>;
  }

  if (!adjustment && !reviewing) {
    return (
      <Screen>
        <ScreenHeader eyebrow="WORKFLOW DE BANCADA" title="Novo ajuste" subtitle="Registre exatamente a decisão tomada pelo colorista." />
        <Callout title="DECISÃO DO OPERADOR" tone="warning">{OPERATOR_QUANTITY_NOTICE}</Callout>
        <ErrorNotice message={error} />
        <SectionHeader>CONTEXTO INFORMADO</SectionHeader>
        <ChoiceRow values={SYSTEMS} selected={form.system} onSelect={(system) => setForm({ ...form, system })} />
        <ChoiceRow values={FINISHES} selected={form.finish} onSelect={(finish) => setForm({ ...form, finish })} />
        <SectionHeader>VOLUME REAL ATUAL · ml</SectionHeader>
        <ChoiceRow values={VOLUME_PRESETS} selected={form.volume} onSelect={(volume) => setForm({ ...form, volume })} />
        <Field value={form.volume} onChangeText={(volume) => setForm({ ...form, volume })} placeholder="Ex.: 450 ou 450,0" keyboardType="decimal-pad" />
        <SectionHeader>PIGMENTOS E MASSAS APLICÁVEIS</SectionHeader>
        {form.components.map((item, index) => (
          <Card key={index}>
            <Field value={item.pigmentCode} onChangeText={(value) => updateComponent(index, 'pigmentCode', value)} placeholder="Código, ex.: BP226" />
            <Field value={item.quantity} onChangeText={(value) => updateComponent(index, 'quantity', value)} placeholder="Massa em g, ex.: 0,10" keyboardType="decimal-pad" />
            {form.components.length > 1 && <ActionButton label="REMOVER COMPONENTE" secondary onPress={() => setForm({ ...form, components: form.components.filter((_, i) => i !== index) })} />}
          </Card>
        ))}
        <ActionButton label="ADICIONAR COMPONENTE" secondary onPress={() => setForm({ ...form, components: [...form.components, { pigmentCode: '', quantity: '' }] })} />
        <SectionHeader>MOTIVO DO AJUSTE</SectionHeader>
        <Field value={form.reason} onChangeText={(reason) => setForm({ ...form, reason })} placeholder="Decisão e objetivo do operador" multiline />
        <ActionButton label="REVISAR AJUSTE" onPress={goToReview} />
      </Screen>
    );
  }

  if (!adjustment && reviewing) {
    const payload = buildAdjustmentPayload(form)!;
    return (
      <Screen>
        <ScreenHeader eyebrow="CONFIRMAÇÃO" title="Revise o ajuste" subtitle="Confira contexto, volume, pigmentos e massas antes de criar o registro." />
        <AdjustmentSummary values={payload} />
        <Callout title="ATENÇÃO" tone="warning">{OPERATOR_QUANTITY_NOTICE}</Callout>
        <ActionButton label="VOLTAR E EDITAR" secondary onPress={() => setReviewing(false)} />
        <ActionButton label="CRIAR REGISTRO PLANEJADO" loading={busy} onPress={() => void createPlanned()} />
      </Screen>
    );
  }

  if (!adjustment) return null;

  const afterOperation = app.activeOperation?.type === 'AFTER' ? app.activeOperation : null;
  return (
    <Screen>
      <ScreenHeader eyebrow="WORKFLOW DE BANCADA" title="Ajuste registrado" subtitle="Acompanhe a aplicação física e a leitura de verificação." />
      <TechnicalRow label="ID" value={`${adjustment.adjustment_id.slice(0, 8)}…`} />
      <TechnicalRow label="Estado" value={presentState(adjustment.lifecycle)} />
      <ErrorNotice message={error ?? app.errorMessage} />
      <AdjustmentSummary values={adjustment} />
      <Callout title="QUANTIDADE INFORMADA" tone="warning">{OPERATOR_QUANTITY_NOTICE}</Callout>

      {adjustment.lifecycle === 'PLANNED' && (
        <>
          {verificationRequired && (
            <Card tone="warning"><Text style={styles.warning}>A resposta da confirmação foi inconclusiva. Verifique o estado antes de qualquer nova ação física.</Text><ActionButton label="VERIFICAR ESTADO" onPress={() => void verifyStatus()} /></Card>
          )}
          {!verificationRequired && <ActionButton label="CONFIRMAR QUE APLIQUEI O AJUSTE" warning onPress={() => setConfirmVisible(true)} />}
        </>
      )}

      {adjustment.lifecycle === 'APPLIED_WAITING_FOR_AFTER' && (
        <>
          <View style={styles.dangerBox}><Text style={styles.dangerText}>{APPLIED_WARNING}</Text><Text style={styles.dangerSub}>A quantidade já foi registrada como aplicada. Faça somente a leitura AFTER.</Text></View>
          <TechnicalRow label="TARGET" value={`#${adjustment.target_measurement_id}`} />
          <TechnicalRow label="BEFORE" value={`#${adjustment.before_measurement_id}`} />
          {afterOperation && <TechnicalRow label="Espera AFTER" value={afterOperation.status} />}
          {(!afterOperation || ['TIMED_OUT', 'CANCELLED', 'FAILED'].includes(afterOperation.status)) && (
            <ActionButton label={afterOperation?.status === 'TIMED_OUT' ? 'TENTAR DETECTAR AFTER NOVAMENTE' : 'PREPARAR LEITURA AFTER'} onPress={() => void app.startAfterCapture(adjustment.adjustment_id, Boolean(afterOperation))} disabled={!app.instrument.connected || app.busy} />
          )}
          {afterOperation && ['PREPARED', 'WAITING'].includes(afterOperation.status) && <ActionButton label="CANCELAR ESPERA" secondary onPress={() => void app.cancelCapture()} />}
          {afterOperation?.status === 'TIMED_OUT' && <ActionButton label="CANCELAR ESPERA E VOLTAR" secondary onPress={() => router.back()} />}
          <ActionButton label="ABANDONAR APÓS APLICAÇÃO" warning onPress={() => setAbandonVisible(true)} />
        </>
      )}

      {adjustment.lifecycle === 'COMPLETED' && <CompletedResult adjustment={adjustment} />}
      {adjustment.lifecycle === 'COMPLETED' && (
        <Card tone="info">
          <SectionHeader>FEEDBACK DO OPERADOR</SectionHeader>
          <ChoiceRow values={['BETTER', 'WORSE', 'SAME', 'UNKNOWN'] as const} selected={visualResult} onSelect={setVisualResult} />
          <ChoiceRow values={['IN_PROGRESS', 'ACCEPTED', 'REJECTED', 'UNKNOWN'] as const} selected={operatorStatus} onSelect={setOperatorStatus} />
          {contradictsInstrument(adjustment.assessment, visualResult) && (
            <Callout title="DIVERGÊNCIA COM O INSTRUMENTO" tone="warning">{OPERATOR_DISAGREEMENT_NOTICE}</Callout>
          )}
          <Field value={observations} onChangeText={setObservations} placeholder="Observações visuais (opcional)" multiline />
          <ActionButton label="SALVAR FEEDBACK" loading={busy} onPress={() => void submitFeedback()} />
        </Card>
      )}
      {adjustment.lifecycle === 'ABANDONED_AFTER_APPLICATION' && <View style={styles.dangerBox}><Text style={styles.dangerText}>AJUSTE ABANDONADO APÓS APLICAÇÃO</Text><Text style={styles.dangerSub}>{adjustment.observations}</Text></View>}

      <Modal visible={confirmVisible} transparent animationType="fade" onRequestClose={() => setConfirmVisible(false)}>
        <View style={styles.modalBackdrop}><View style={styles.modalCard}>
          <Text style={styles.modalTitle}>CONFIRMAÇÃO FÍSICA</Text>
          <Text style={styles.modalText}>Confirme somente se estes pigmentos e estas massas já foram adicionados fisicamente à tinta. Esta ação bloqueia a edição e inicia a espera pela leitura AFTER.</Text>
          <AdjustmentSummary values={adjustment} />
          <ActionButton label="SIM, JÁ APLIQUEI FISICAMENTE" warning loading={busy} onPress={() => void confirmApplied()} />
          <ActionButton label="NÃO, VOLTAR" secondary onPress={() => setConfirmVisible(false)} />
        </View></View>
      </Modal>

      <Modal visible={abandonVisible} transparent animationType="fade" onRequestClose={() => setAbandonVisible(false)}>
        <View style={styles.modalBackdrop}><View style={styles.modalCard}>
          <Text style={styles.modalTitle}>ABANDONAR AJUSTE APLICADO?</Text>
          <Text style={styles.modalText}>O registro físico será preservado como ABANDONED_AFTER_APPLICATION. Nenhum AFTER será inventado ou associado.</Text>
          <Field value={abandonReason} onChangeText={setAbandonReason} placeholder="Motivo obrigatório" multiline />
          <ActionButton label="CONFIRMAR ABANDONO" warning disabled={!abandonReason.trim()} onPress={() => void abandon()} />
          <ActionButton label="VOLTAR" secondary onPress={() => setAbandonVisible(false)} />
        </View></View>
      </Modal>
    </Screen>
  );
}

function AdjustmentSummary({ values }: { values: Pick<Adjustment, 'system' | 'finish' | 'volume_ml' | 'components' | 'operator_reason'> | ReturnType<typeof buildAdjustmentPayload> }) {
  if (!values) return null;
  return <Card>
    <TechnicalRow label="Sistema" value={values.system} />
    <TechnicalRow label="Acabamento" value={values.finish} />
    <TechnicalRow label="Volume" value={`${values.volume_ml} ml`} />
    {values.components.map((item) => <TechnicalRow key={item.pigment_code} label={item.pigment_code} value={`${item.quantity_g} g`} />)}
    <Text style={uiStyles.muted}>Motivo: {values.operator_reason}</Text>
  </Card>;
}

function CompletedResult({ adjustment }: { adjustment: Adjustment }) {
  const result = completedResultData(adjustment);
  if (!result) return null;
  return <>
    {adjustment.assessment && <VerdictCard assessment={adjustment.assessment} />}
    <SectionHeader>CADEIA EXPERIMENTAL</SectionHeader>
    <Card>
      <TechnicalRow label="TARGET" value={`#${result.targetMeasurementId}`} />
      <TechnicalRow label="BEFORE" value={`#${result.beforeMeasurementId}`} />
      <TechnicalRow label="AFTER" value={`#${result.afterMeasurementId}`} />
      <TechnicalRow label="Pior ângulo antes" value={`${result.worstAngleBefore}°`} />
      <TechnicalRow label="Pior ângulo depois" value={`${result.worstAngleAfter}°`} />
    </Card>
    <SectionHeader>RESPOSTA OBSERVADA · AFTER − BEFORE</SectionHeader>
    {result.observedResponse.map((item) => <Card key={item.angle}>
      <Text style={styles.angle}>{item.angle}°</Text>
      <TechnicalRow label="Resposta L*" value={formatSigned(item.response_l)} />
      <TechnicalRow label="Resposta a*" value={formatSigned(item.response_a)} />
      <TechnicalRow label="Resposta b*" value={formatSigned(item.response_b)} />
    </Card>)}
    <SectionHeader>RESULTADO VS. TARGET</SectionHeader>
    {result.outcomes.map((item) => <Card key={item.angle}>
      <Text style={styles.angle}>{item.angle}° · {item.delta_e_outcome}</Text>
      <TechnicalRow label="ΔE antes" value={item.before_delta_e76.toFixed(3)} />
      <TechnicalRow label="ΔE depois" value={item.after_delta_e76.toFixed(3)} />
      <TechnicalRow label="Variação de erro" value={formatSigned(item.delta_e_improvement)} />
      <TechnicalRow label="L*" value={item.lightness_outcome} />
      <TechnicalRow label="a*" value={item.red_green_outcome} />
      <TechnicalRow label="b*" value={item.yellow_blue_outcome} />
    </Card>)}
  </>;
}

function contradictsInstrument(assessment: TrialAssessment | null, visualResult: string): boolean {
  if (!assessment) return false;
  return (visualResult === 'BETTER' && assessment.verdict === 'WORSENED')
    || (visualResult === 'WORSE' && assessment.verdict === 'IMPROVED');
}

function VerdictCard({ assessment }: { assessment: TrialAssessment }) {
  const verdict = presentVerdict(assessment.verdict);
  const findings = assessmentFindings(assessment);
  const accent = { success: colors.success, danger: colors.danger, warning: colors.warning, info: colors.technical }[verdict.tone];
  return <Card tone={verdict.tone}>
    <Text style={styles.verdictEyebrow}>ANÁLISE DO INSTRUMENTO</Text>
    <Text style={[styles.verdictTitle, { color: accent }]}>{verdict.title}</Text>
    <Text style={styles.verdictDescription}>{verdict.description}</Text>
    <TechnicalRow
      label="Maior ΔE"
      value={`${assessment.worst_delta_e_before.toFixed(2)} → ${assessment.worst_delta_e_after.toFixed(2)}`}
    />
    {assessment.worsened_angles.length > 0 && (
      <TechnicalRow label="Pioraram" value={assessment.worsened_angles.map((angle) => `${angle}°`).join(' · ')} />
    )}
    {assessment.improved_angles.length > 0 && (
      <TechnicalRow label="Melhoraram" value={assessment.improved_angles.map((angle) => `${angle}°`).join(' · ')} />
    )}
    {findings.map((item) => <Text key={item.key} style={styles.verdictFinding}>• {item.text}</Text>)}
    <Text style={uiStyles.muted}>
      Variações abaixo de {assessment.delta_e_noise.toFixed(2)} ΔE são tratadas como ruído. Esta análise não depende do feedback visual.
    </Text>
  </Card>;
}

function ChoiceRow<T extends string>({ values, selected, onSelect }: { values: readonly T[]; selected: string; onSelect: (value: T) => void }) {
  return <View style={styles.choices}>{values.map((value) => <Pressable key={value} onPress={() => onSelect(value)} style={[styles.choice, selected === value && styles.choiceSelected]}><Text style={[styles.choiceText, selected === value && styles.choiceTextSelected]}>{value}</Text></Pressable>)}</View>;
}

const styles = StyleSheet.create({
  warning: { color: colors.warning, fontSize: 16, fontWeight: '800', lineHeight: 23 },
  dangerBox: { backgroundColor: '#3B1113', borderColor: colors.danger, borderRadius: radius.md, borderWidth: 2, gap: spacing.sm, padding: spacing.md },
  dangerText: { color: colors.danger, fontSize: 20, fontWeight: '900', textAlign: 'center' },
  dangerSub: { color: colors.textPrimary, fontSize: 16, lineHeight: 23, textAlign: 'center' },
  choices: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  choice: { backgroundColor: colors.surfaceElevated, borderColor: colors.border, borderRadius: radius.sm, borderWidth: 1, padding: 12 },
  choiceSelected: { borderColor: colors.technical },
  choiceText: { color: colors.textSecondary, fontWeight: '700' },
  choiceTextSelected: { color: colors.technical },
  modalBackdrop: { backgroundColor: '#000B', flex: 1, justifyContent: 'center', padding: spacing.md },
  modalCard: { backgroundColor: colors.surface, borderColor: colors.warning, borderRadius: radius.md, borderWidth: 2, gap: spacing.md, maxHeight: '90%', padding: spacing.md },
  modalTitle: { color: colors.warning, fontSize: 22, fontWeight: '900' },
  modalText: { color: colors.textPrimary, fontSize: 16, lineHeight: 24 },
  angle: { color: colors.textPrimary, fontSize: 19, fontWeight: '900' },
  verdictEyebrow: { color: colors.textSecondary, fontSize: 10, fontWeight: '900', letterSpacing: 1.2 },
  verdictTitle: { fontSize: 26, fontWeight: '900' },
  verdictDescription: { color: colors.textPrimary, fontSize: 15, lineHeight: 22 },
  verdictFinding: { color: colors.textPrimary, fontSize: 14, lineHeight: 20 },
});
