import { router } from 'expo-router';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { MandacorApiClient } from '@/src/api/client';
import { friendlyError } from '@/src/api/errors';
import {
  ActionButton,
  Card,
  EmptyState,
  ErrorNotice,
  Screen,
  ScreenHeader,
  SectionHeader,
  TechnicalRow,
  uiStyles,
} from '@/src/components/ui';
import { ColorPlaneChart } from '@/src/components/ColorPlaneChart';
import {
  assessElongation,
  configuredElongationTolerance,
} from '@/src/features/results/elongation';
import { presentAction, presentDirection } from '@/src/presentation/format';
import { useMandacor } from '@/src/state/AppContext';
import { colors, radius, spacing } from '@/src/theme/tokens';
import {
  Comparison,
  CorrectionActions,
  CorrectionNeed,
  Diagnosis,
  FinishType,
  PaintSystem,
  PigmentCandidate,
  PigmentRecommendation,
  RequiredAngle,
} from '@/src/types/api';

const SYSTEMS: PaintSystem[] = ['POLYESTER_BASECOAT', 'PU', 'UNKNOWN'];
const FINISHES: FinishType[] = ['SOLID', 'METALLIC', 'PEARL', 'UNKNOWN'];

export default function ResultsScreen() {
  const { baseUrl, currentSession, pendingAdjustment } = useMandacor();
  const client = useMemo(() => new MandacorApiClient(baseUrl), [baseUrl]);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [diagnosis, setDiagnosis] = useState<Diagnosis | null>(null);
  const [correction, setCorrection] = useState<CorrectionNeed | null>(null);
  const [pigments, setPigments] = useState<PigmentRecommendation | null>(null);
  const [system, setSystem] = useState<PaintSystem>('UNKNOWN');
  const [finish, setFinish] = useState<FinishType>('UNKNOWN');
  const [selectedAngle, setSelectedAngle] = useState<RequiredAngle>(45);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadResults = useCallback(async () => {
    if (!currentSession || currentSession.state !== 'READY_FOR_COMPARISON') return;
    setLoading(true);
    setError(null);
    try {
      const [comparisonResult, diagnosisResult, correctionResult] = await Promise.all([
        client.comparison(currentSession.session_id),
        client.diagnosis(currentSession.session_id),
        client.correction(currentSession.session_id),
      ]);
      setComparison(comparisonResult);
      setDiagnosis(diagnosisResult);
      setCorrection(correctionResult);
    } catch (caught) {
      setError(friendlyError(caught));
    } finally {
      setLoading(false);
    }
  }, [client, currentSession]);

  useEffect(() => {
    void loadResults();
  }, [loadResults]);

  const loadPigments = async () => {
    if (!currentSession) return;
    setLoading(true);
    setError(null);
    try {
      setPigments(await client.pigmentCandidates(currentSession.session_id, system, finish));
    } catch (caught) {
      setError(friendlyError(caught));
    } finally {
      setLoading(false);
    }
  };

  if (!currentSession || currentSession.state !== 'READY_FOR_COMPARISON') {
    return (
      <Screen>
        <ScreenHeader eyebrow="RESULTADO COLORIMÉTRICO" title="Como está a amostra" subtitle="Capture a cor alvo e a amostra para liberar a comparação." />
        <EmptyState>A sessão ainda não está pronta. Capture alvo e amostra primeiro.</EmptyState>
      </Screen>
    );
  }

  const worst = comparison?.angles.find((item) => item.angle === diagnosis?.worst_angle);
  const selectedTarget = currentSession.target?.angles.find((item) => item.angle === selectedAngle);
  const selectedSample = currentSession.sample?.angles.find((item) => item.angle === selectedAngle);
  const selectedDelta = comparison?.angles.find((item) => item.angle === selectedAngle);
  const selectedDiagnosis = diagnosis?.angles.find((item) => item.angle === selectedAngle);
  const elongation = comparison
    ? assessElongation(
      comparison.angles,
      configuredElongationTolerance(process.env.EXPO_PUBLIC_ELONGATION_TOLERANCE),
    )
    : null;

  return (
    <Screen>
      <ScreenHeader
        eyebrow="RESULTADO COLORIMÉTRICO"
        title="Como está a amostra"
        subtitle="Todos os desvios usam a cor alvo como ponto zero. Selecione um ângulo para analisar."
      />
      <ErrorNotice message={error} />
      {!comparison && <ActionButton label="CARREGAR RESULTADO" onPress={() => void loadResults()} disabled={loading} />}

      {elongation && (
        <Card tone={elongation.passes ? 'success' : 'danger'}>
          <View style={styles.elongationHeader}>
            <View style={[
              styles.elongationIcon,
              elongation.passes ? styles.elongationIconPass : styles.elongationIconFail,
            ]}>
              <Text style={styles.elongationIconText}>{elongation.passes ? '✓' : '!'}</Text>
            </View>
            <View style={styles.elongationHeading}>
              <Text style={styles.elongationEyebrow}>ALONGAMENTO</Text>
              <Text style={[
                styles.elongationResult,
                { color: elongation.passes ? colors.success : colors.danger },
              ]}>
                {elongation.passes ? 'PASSA NO ALONGAMENTO' : 'NÃO PASSA NO ALONGAMENTO'}
              </Text>
            </View>
          </View>
          <Text style={styles.elongationDescription}>
            {elongation.passes
              ? 'A variação da luminosidade entre os ângulos está dentro da referência.'
              : 'A curva de luminosidade da amostra se afastou da referência entre os ângulos.'}
          </Text>
          <View style={styles.elongationMetrics}>
            <View style={styles.elongationMetric}>
              <Text style={styles.elongationMetricLabel}>VARIAÇÃO</Text>
              <Text style={styles.elongationMetricValue}>{elongation.variation.toFixed(2)} ΔL*</Text>
            </View>
            <View style={styles.elongationMetric}>
              <Text style={styles.elongationMetricLabel}>LIMITE ATUAL</Text>
              <Text style={styles.elongationMetricValue}>≤ {elongation.tolerance.toFixed(2)} ΔL*</Text>
            </View>
          </View>
          <Text style={uiStyles.muted}>
            Maior abertura: {elongation.highestAngle}° a {elongation.lowestAngle}°. Esta avaliação considera somente o alongamento; a cor deve ser analisada separadamente.
          </Text>
        </Card>
      )}

      {diagnosis && worst && (
        <Card tone="warning">
          <SectionHeader>MAIOR DESVIO</SectionHeader>
          <View style={styles.worstHero}>
            <View>
              <Text style={styles.worstLabel}>ÂNGULO</Text>
              <Text style={styles.worst}>{diagnosis.worst_angle}°</Text>
            </View>
            <View style={styles.worstMetric}>
              <Text style={styles.worstLabel}>ΔE76</Text>
              <Text style={styles.worstValue}>{worst.delta_e76.toFixed(3)}</Text>
            </View>
          </View>
          <TechnicalRow
            label="Dominante"
            value={diagnosis.angles.find((item) => item.angle === diagnosis.worst_angle)?.dominant_axis ?? '—'}
          />
          <Text style={uiStyles.muted}>Indicador de maior magnitude; não representa aprovação ou reprovação.</Text>
        </Card>
      )}

      {selectedTarget && selectedSample && (
        <Card tone="info">
          <SectionHeader>MAPA DE COR · a* × b*</SectionHeader>
          <Text style={uiStyles.muted}>O alvo é o ponto zero. O marcador mostra somente como está a amostra.</Text>
          <ColorPlaneChart
            selectedAngle={selectedAngle}
            onSelectAngle={setSelectedAngle}
            target={selectedTarget}
            sample={selectedSample}
          />
          {selectedDiagnosis && (
            <View style={styles.sampleSummary}>
              <Text style={styles.sampleSummaryLabel}>AMOSTRA · {selectedAngle}°</Text>
              <Text style={styles.sampleSummaryText}>
                {presentDirection(selectedDiagnosis.lightness)} · {presentDirection(selectedDiagnosis.red_green)} · {presentDirection(selectedDiagnosis.yellow_blue)}
              </Text>
            </View>
          )}
          {selectedDelta && (
            <View style={styles.deltaStrip}>
              <Text style={styles.deltaText}>Δa {selectedDelta.delta_a >= 0 ? '+' : ''}{selectedDelta.delta_a.toFixed(3)}</Text>
              <Text style={styles.deltaText}>Δb {selectedDelta.delta_b >= 0 ? '+' : ''}{selectedDelta.delta_b.toFixed(3)}</Text>
              <Text style={styles.deltaText}>ΔE {selectedDelta.delta_e76.toFixed(3)}</Text>
            </View>
          )}
        </Card>
      )}

      {diagnosis && (
        <>
          <SectionHeader>VISÃO DE BANCADA</SectionHeader>
          <SummaryCard title="FRENTE · 15° / 25°" values={diagnosis.front} presenter={presentDirection} />
          <SummaryCard title="45°" values={diagnosis.mid} presenter={presentDirection} />
          <SummaryCard title="FLOP · 75° / 105°" values={diagnosis.flop} presenter={presentDirection} />
        </>
      )}

      {correction && (
        <>
          <SectionHeader>O QUE A TINTA PRECISA</SectionHeader>
          <SummaryCard title="FRENTE" values={correction.front} presenter={presentAction} />
          <SummaryCard title="45°" values={correction.mid} presenter={presentAction} />
          <SummaryCard title="FLOP" values={correction.flop} presenter={presentAction} />
          <Card>
            <TechnicalRow label="Questão principal" value={`${correction.primary_issue.angle}° · ${correction.primary_issue.axis}`} />
            <TechnicalRow label="Ação" value={correction.primary_issue.action ? presentAction(correction.primary_issue.action) : 'SEM AÇÃO'} />
          </Card>
        </>
      )}

      <SectionHeader>ANÁLISE DE PIGMENTOS</SectionHeader>
      <Text style={uiStyles.muted}>O contexto é informado pelo operador; não é inferido da leitura.</Text>
      <ChoiceRow label="Sistema" values={SYSTEMS} selected={system} onSelect={setSystem} />
      <ChoiceRow label="Acabamento" values={FINISHES} selected={finish} onSelect={setFinish} />
      <ActionButton label="CONSULTAR CANDIDATOS" onPress={() => void loadPigments()} disabled={loading} />

      {pigments && (
        <>
          {pigments.no_single_safe_candidate && (
            <View style={styles.alert}>
              <Text style={styles.alertTitle}>NENHUM PIGMENTO ÚNICO É SEGURO</Text>
              <Text style={styles.alertText}>Nenhum pigmento único é seguro para todos os desvios atuais. Faça teste de bancada.</Text>
            </View>
          )}
          <Text style={styles.noDose}>MANDACOR ainda não calcula quantidade.</Text>
          {pigments.candidates.map((item) => <CandidateCard key={item.pigment_code} item={item} />)}
          {pigments.rejected_candidates.length > 0 && <SectionHeader>EVITAR</SectionHeader>}
          {pigments.rejected_candidates.map((item) => <CandidateCard key={item.pigment_code} item={item} rejected />)}
        </>
      )}

      <SectionHeader>WORKFLOW DE BANCADA</SectionHeader>
      <Text style={uiStyles.muted}>Registre somente a quantidade e o volume decididos pelo operador.</Text>
      <ActionButton
        label={pendingAdjustment ? 'CONTINUAR AFTER PENDENTE' : 'NOVO AJUSTE'}
        warning={Boolean(pendingAdjustment)}
        onPress={() => router.push(pendingAdjustment ? `../adjustment?id=${pendingAdjustment.adjustment_id}` : '../adjustment')}
      />
    </Screen>
  );
}

function SummaryCard({
  title,
  values,
  presenter,
}: {
  title: string;
  values: CorrectionActions;
  presenter: (value: string) => string;
}) {
  return (
    <Card tone="info">
      <Text style={styles.angleTitle}>{title}</Text>
      <TechnicalRow label="L*" value={presenter(values.lightness)} />
      <TechnicalRow label="a*" value={presenter(values.red_green)} />
      <TechnicalRow label="b*" value={presenter(values.yellow_blue)} />
    </Card>
  );
}

function ChoiceRow<T extends string>({
  label,
  values,
  selected,
  onSelect,
}: {
  label: string;
  values: readonly T[];
  selected: T;
  onSelect: (value: T) => void;
}) {
  return (
    <View style={styles.choiceSection}>
      <Text style={styles.choiceLabel}>{label}</Text>
      <View style={styles.choiceRow}>
        {values.map((value) => (
          <Text
            accessibilityRole="button"
            key={value}
            onPress={() => onSelect(value)}
            style={[styles.choice, selected === value && styles.choiceSelected]}
          >
            {value}
          </Text>
        ))}
      </View>
    </View>
  );
}

function CandidateCard({ item, rejected = false }: { item: PigmentCandidate; rejected?: boolean }) {
  const assessment = (values: PigmentCandidate['matched_needs']) =>
    values.length ? values.map((value) => `${value.angle}° ${value.axis}: ${value.need}`).join(' · ') : '—';
  return (
    <Card>
      <Text style={[styles.candidateCode, rejected && { color: colors.danger }]}>{item.pigment_code}</Text>
      <TechnicalRow label="Status" value={item.status} />
      <Text style={styles.detailLabel}>AJUDA EM</Text>
      <Text style={uiStyles.muted}>{assessment(item.matched_needs)}</Text>
      <Text style={styles.detailLabel}>CONFLITA EM</Text>
      <Text style={uiStyles.muted}>{assessment(item.conflicts)}</Text>
      <Text style={styles.detailLabel}>RISCOS</Text>
      <Text style={uiStyles.muted}>{item.risks.join(' · ') || '—'}</Text>
      <Text style={styles.detailLabel}>DESCONHECIDO</Text>
      <Text style={uiStyles.muted}>{assessment(item.unknown_effects)}</Text>
      <Text style={styles.detailLabel}>MOTIVO</Text>
      <Text style={uiStyles.muted}>{[...item.contraindications, ...item.rationale].join(' · ') || '—'}</Text>
    </Card>
  );
}

const styles = StyleSheet.create({
  elongationHeader: { alignItems: 'center', flexDirection: 'row', gap: spacing.mdSm },
  elongationIcon: {
    alignItems: 'center',
    borderRadius: 24,
    height: 46,
    justifyContent: 'center',
    width: 46,
  },
  elongationIconPass: { backgroundColor: colors.successSoft, borderColor: colors.success, borderWidth: 1 },
  elongationIconFail: { backgroundColor: colors.dangerSoft, borderColor: colors.danger, borderWidth: 1 },
  elongationIconText: { color: colors.textPrimary, fontSize: 24, fontWeight: '900' },
  elongationHeading: { flex: 1, gap: 3 },
  elongationEyebrow: { color: colors.textSecondary, fontSize: 10, fontWeight: '900', letterSpacing: 1.2 },
  elongationResult: { fontSize: 18, fontWeight: '900', lineHeight: 23 },
  elongationDescription: { color: colors.textPrimary, fontSize: 14, lineHeight: 20 },
  elongationMetrics: { flexDirection: 'row', gap: spacing.sm },
  elongationMetric: {
    backgroundColor: colors.surfaceElevated,
    borderRadius: radius.sm,
    flex: 1,
    gap: 4,
    padding: spacing.mdSm,
  },
  elongationMetricLabel: { color: colors.textSecondary, fontSize: 9, fontWeight: '900', letterSpacing: 0.8 },
  elongationMetricValue: { color: colors.textPrimary, fontFamily: 'SpaceMono', fontSize: 14 },
  worstHero: { alignItems: 'flex-end', flexDirection: 'row', justifyContent: 'space-between' },
  worstLabel: { color: colors.textSecondary, fontSize: 10, fontWeight: '900', letterSpacing: 1 },
  worst: { color: colors.textPrimary, fontSize: 40, fontWeight: '900' },
  worstMetric: { alignItems: 'flex-end' },
  worstValue: { color: colors.warning, fontFamily: 'SpaceMono', fontSize: 24 },
  deltaStrip: { flexDirection: 'row', justifyContent: 'space-between' },
  deltaText: { color: colors.technical, fontFamily: 'SpaceMono', fontSize: 11 },
  sampleSummary: { backgroundColor: '#102437', borderRadius: radius.sm, gap: 4, padding: spacing.sm },
  sampleSummaryLabel: { color: colors.technical, fontSize: 10, fontWeight: '900', letterSpacing: 0.6 },
  sampleSummaryText: { color: colors.textPrimary, fontSize: 14, fontWeight: '900', lineHeight: 20, textAlign: 'center' },
  angleTitle: { color: colors.textPrimary, fontSize: 20, fontWeight: '900' },
  alert: { backgroundColor: '#4A3610', borderColor: colors.warning, borderRadius: radius.md, borderWidth: 1, gap: spacing.sm, padding: spacing.md },
  alertTitle: { color: colors.warning, fontSize: 17, fontWeight: '900' },
  alertText: { color: colors.textPrimary, fontSize: 16, lineHeight: 23 },
  noDose: { color: colors.warning, fontSize: 17, fontWeight: '900', textAlign: 'center' },
  choiceSection: { gap: spacing.sm },
  choiceLabel: { color: colors.textPrimary, fontWeight: '800' },
  choiceRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  choice: { backgroundColor: colors.surfaceElevated, borderColor: colors.border, borderRadius: radius.sm, borderWidth: 1, color: colors.textSecondary, minHeight: 42, paddingHorizontal: 12, paddingVertical: 11 },
  choiceSelected: { borderColor: colors.technical, color: colors.technical },
  candidateCode: { color: colors.technical, fontFamily: 'SpaceMono', fontSize: 24, fontWeight: '900' },
  detailLabel: { color: colors.textPrimary, fontSize: 12, fontWeight: '900', letterSpacing: 1 },
});
