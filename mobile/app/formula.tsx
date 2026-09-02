import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Alert, Modal, Pressable, StyleSheet, Text, View } from 'react-native';

import { MandacorApiClient } from '@/src/api/client';
import { friendlyError } from '@/src/api/errors';
import { ActionButton, Callout, Card, EmptyState, ErrorNotice, Field, Screen, ScreenHeader, SectionHeader, TechnicalRow } from '@/src/components/ui';
import { useMandacor } from '@/src/state/AppContext';
import {
  customQuantityMultiplier,
  customQuantityUnit,
  formulaQuantityOptions,
  scaleFormulaWeight,
} from '@/src/features/formulas/quantity';
import { colors, radius, spacing } from '@/src/theme/tokens';
import { FormulaProduct, FormulaReading, MetallicGrain } from '@/src/types/api';

const METALLIC_GRAINS: Array<{ value: MetallicGrain; label: string }> = [
  { value: 'FINO', label: 'FINO' },
  { value: 'MEDIO_FINO', label: 'MÉDIO FINO' },
  { value: 'MEDIO', label: 'MÉDIO' },
  { value: 'GROSSEIRO', label: 'GROSSEIRO' },
  { value: 'MUITO_GROSSEIRO', label: 'MUITO GROSSEIRO' },
];

const ACTIVE_CAPTURE_STATES = new Set(['PREPARED', 'WAITING']);

function grams(value: string): string {
  return `${Number(value).toLocaleString('pt-BR', { maximumFractionDigits: 4 })} g`;
}

export default function FormulaScreen() {
  const parameters = useLocalSearchParams<{ code?: string | string[] }>();
  const code = Array.isArray(parameters.code) ? parameters.code[0] : parameters.code;
  const app = useMandacor();
  const client = useMemo(() => new MandacorApiClient(app.baseUrl), [app.baseUrl]);
  const [formula, setFormula] = useState<FormulaProduct | null>(null);
  const [selectedQuantities, setSelectedQuantities] = useState<Record<number, string>>({});
  const [customQuantities, setCustomQuantities] = useState<Record<number, string>>({});
  const [readings, setReadings] = useState<FormulaReading[]>([]);
  const [readingFormulaId, setReadingFormulaId] = useState<number | null>(null);
  const [metallicGrain, setMetallicGrain] = useState<MetallicGrain | null>(null);
  const [readingNotes, setReadingNotes] = useState('');
  const [savingReading, setSavingReading] = useState(false);
  const [readingSaved, setReadingSaved] = useState(false);
  const [captureRequested, setCaptureRequested] = useState(false);
  const [showPrepareModal, setShowPrepareModal] = useState(false);
  const [selectedMeasurementId, setSelectedMeasurementId] = useState<number | null>(null);
  const captureBaselineId = useRef<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!code) return;
    client.getFormula(code).then(setFormula).catch((caught) => setError(friendlyError(caught)));
    client.formulaReadings(code).then(setReadings).catch(() => undefined);
  }, [client, code]);

  const sample = app.currentSession?.sample ?? null;
  const activeOperation = app.activeOperation;
  const sampleCapture = activeOperation?.session_id === app.currentSession?.session_id
    && activeOperation?.type === 'SAMPLE'
    ? activeOperation
    : null;
  const captureActive = Boolean(sampleCapture && ACTIVE_CAPTURE_STATES.has(sampleCapture.status));

  useEffect(() => {
    if (!captureRequested || !sample) return;
    if (sample.measurement_id === captureBaselineId.current) return;
    setSelectedMeasurementId(sample.measurement_id);
    setCaptureRequested(false);
    setReadingSaved(false);
  }, [captureRequested, sample]);

  useEffect(() => {
    if (selectedMeasurementId !== null && sample?.measurement_id !== selectedMeasurementId) {
      setSelectedMeasurementId(null);
    }
  }, [sample, selectedMeasurementId]);

  const prepareNewReading = () => {
    if (!app.currentSession?.target || captureActive) return;
    setShowPrepareModal(false);
    app.clearError();
    captureBaselineId.current = sample?.measurement_id ?? null;
    setSelectedMeasurementId(null);
    setCaptureRequested(true);
    setReadingSaved(false);
    void app.prepareCapture('sample');
  };

  const saveReading = async () => {
    if (!formula || !app.currentSession?.sample || readingFormulaId === null) return;
    if (app.currentSession.sample.measurement_id !== selectedMeasurementId) return;
    setSavingReading(true);
    setError(null);
    try {
      const saved = await client.saveFormulaReading(
        formula.code, app.currentSession.session_id, readingFormulaId, metallicGrain, readingNotes,
      );
      setReadings((current) => [saved, ...current]);
      setFormula((current) => current ? { ...current, reading_count: current.reading_count + 1 } : current);
      setReadingSaved(true);
      setSelectedMeasurementId(null);
      setReadingFormulaId(null);
      setReadingNotes('');
    } catch (caught) {
      setError(friendlyError(caught));
    } finally {
      setSavingReading(false);
    }
  };

  const deleteFormula = () => {
    if (!formula) return;
    Alert.alert(
      'Remover tinta?',
      `${formula.display_code} · ${formula.description}\n\nAs leituras já salvas serão preservadas no dataset.`,
      [
        { text: 'CANCELAR', style: 'cancel' },
        { text: 'REMOVER', style: 'destructive', onPress: async () => {
          try {
            await client.deleteFormula(formula.code);
            router.replace('/formulas');
          } catch (caught) {
            setError(friendlyError(caught));
          }
        } },
      ],
    );
  };

  const isMetallic = Boolean(formula?.finish_label.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase().includes('METAL'));

  return <Screen>
    <Modal
      animationType="fade"
      onRequestClose={() => setShowPrepareModal(false)}
      transparent
      visible={showPrepareModal}
    >
      <View style={styles.modalBackdrop}>
        <View accessibilityRole="alert" style={styles.modalCard}>
          <Text style={styles.modalEyebrow}>PREPARAR LEITURA</Text>
          <Text style={styles.modalTitle}>Fazer uma nova leitura?</Text>
          <Text style={styles.modalText}>
            O sistema registrará as medições que já existem e aguardará uma nova leitura desta tinta/amostra.
          </Text>
          <View style={app.instrument.connected ? styles.modalInfo : styles.modalWarning}>
            <Text style={app.instrument.connected ? styles.modalInfoText : styles.modalWarningText}>
              {app.instrument.connected
                ? 'Depois de iniciar, faça a leitura no espectrofotômetro. A última leitura já armazenada não será usada.'
                : 'O espectrofotômetro está desconectado. Conecte o aparelho antes de preparar a leitura.'}
            </Text>
          </View>
          {app.instrument.connected ? <ActionButton
            label="INICIAR E AGUARDAR NOVA LEITURA"
            disabled={app.busy}
            onPress={prepareNewReading}
          /> : <ActionButton
            label="IR PARA CONEXÃO"
            onPress={() => {
              setShowPrepareModal(false);
              router.push('/');
            }}
          />}
          <ActionButton label="CANCELAR" secondary onPress={() => setShowPrepareModal(false)} />
        </View>
      </View>
    </Modal>
    <ActionButton label="‹ VOLTAR À BUSCA" secondary onPress={() => router.back()} />
    <ScreenHeader eyebrow="FÓRMULA SKYMIX" title={formula?.description ?? 'Carregando fórmula'} subtitle={formula ? `${formula.system_label} · ${formula.paint_line}` : undefined} />
    <ErrorNotice message={error ?? app.errorMessage} />
    {!formula && !error && <EmptyState>Carregando componentes e quantidades...</EmptyState>}
    {formula && <>
      <Card>
        <TechnicalRow label="Código" value={formula.display_code} />
        {!!formula.universal_code && <TechnicalRow label="Cód. universal" value={formula.universal_code} />}
        {!!formula.manufacturer && <TechnicalRow label="Montadora" value={formula.manufacturer} />}
        {!!formula.year && <TechnicalRow label="Ano" value={formula.year} />}
        {!!formula.finish_label && <TechnicalRow label="Aspecto" value={formula.finish_label} />}
        {!!formula.nuance && <TechnicalRow label="Nuance" value={formula.nuance} />}
        <TechnicalRow label="Origem" value={formula.origin === 'USER' ? 'Cadastro do usuário' : 'SkyMix'} />
        <TechnicalRow label="Leituras no dataset" value={String(formula.reading_count)} />
      </Card>
      <View style={styles.managementButtons}>
        <ActionButton label="EDITAR TINTA" secondary onPress={() => router.push({ pathname: '/formula-editor', params: { code: formula.code } })} />
        <ActionButton label="REMOVER TINTA" warning onPress={deleteFormula} />
      </View>
      <Card tone="success">
        <SectionHeader>DATASET DO ESPECTROFOTÔMETRO</SectionHeader>
        <Text style={styles.datasetText}>Salve a leitura capturada como TINTA / AMOSTRA nesta cor. Os cinco ângulos e os 15 valores Lab serão preservados.</Text>
        <Text style={styles.quantityTitle}>FÓRMULA REAL USADA · OBRIGATÓRIO</Text>
        <View style={styles.readingFormulaOptions}>{formula.variants.map((variant) => <Pressable
          accessibilityRole="button"
          accessibilityState={{ selected: readingFormulaId === variant.formula_id }}
          key={variant.formula_id}
          onPress={() => setReadingFormulaId(variant.formula_id)}
          style={[styles.readingFormulaOption, readingFormulaId === variant.formula_id && styles.quantityOptionSelected]}
        >
          <Text style={[styles.quantityText, readingFormulaId === variant.formula_id && styles.quantityTextSelected]}>
            {variant.condition} · {variant.package} · V{variant.version}
          </Text>
        </Pressable>)}</View>
        {isMetallic && <>
          <Text style={styles.quantityTitle}>TAMANHO DO METÁLICO · OBRIGATÓRIO</Text>
          <View style={styles.quantityOptions}>{METALLIC_GRAINS.map((grain) => <Pressable
            key={grain.value}
            onPress={() => setMetallicGrain(grain.value)}
            style={[styles.quantityOption, metallicGrain === grain.value && styles.quantityOptionSelected]}
          ><Text style={[styles.quantityText, metallicGrain === grain.value && styles.quantityTextSelected]}>{grain.label}</Text></Pressable>)}</View>
        </>}
        <Field multiline value={readingNotes} onChangeText={setReadingNotes} placeholder="Observação da leitura (opcional)" />
        {app.currentSession?.target ? <>
          {captureActive ? <View style={styles.captureNotice}>
            <Text style={styles.captureTitle}>AGUARDANDO NOVA LEITURA</Text>
            <Text style={styles.captureText}>Faça agora a leitura desta tinta/amostra no espectrofotômetro. Somente uma medição nova será aceita.</Text>
            <ActionButton label="CANCELAR ESPERA" warning disabled={app.busy} onPress={() => void app.cancelCapture()} />
          </View> : <ActionButton
            label={selectedMeasurementId === null ? 'PREPARAR NOVA LEITURA' : 'FAZER OUTRA LEITURA'}
            secondary
            disabled={app.busy}
            onPress={() => {
              app.clearError();
              setShowPrepareModal(true);
            }}
          />}
          {selectedMeasurementId !== null && sample?.measurement_id === selectedMeasurementId ?
            <TechnicalRow label="Nova leitura selecionada" value={`#${selectedMeasurementId}`} /> :
            !captureActive && <Text style={styles.datasetWarning}>Nenhuma leitura selecionada. Prepare e faça uma nova leitura para salvar no dataset.</Text>}
          <ActionButton
            label="SALVAR LEITURA NO DATASET"
            loading={savingReading}
            disabled={selectedMeasurementId === null || readingFormulaId === null || (isMetallic && !metallicGrain)}
            onPress={() => void saveReading()}
          />
        </> : <>
          <Text style={styles.datasetWarning}>Capture primeiro a cor alvo na tela Medir. Depois você poderá preparar uma nova leitura da tinta aqui.</Text>
          <ActionButton label="IR PARA MEDIÇÃO" secondary onPress={() => router.push('/measure')} />
        </>}
        {readingSaved && <Text style={styles.saved}>LEITURA SALVA COM SUCESSO</Text>}
        {readings.slice(0, 3).map((reading) => <View key={reading.reading_id} style={styles.readingRow}>
          <Text style={styles.readingTitle}>LEITURA #{reading.measurement_id}</Text>
          <Text style={styles.readingDetail}>{new Date(reading.created_at).toLocaleString('pt-BR')}{reading.metallic_grain ? ` · ${reading.metallic_grain.replaceAll('_', ' ')}` : ''}</Text>
          <Text style={reading.quality_status === 'eligible' ? styles.readingEligible : styles.readingReview}>
            {reading.quality_status === 'eligible' ? 'DADOS APTOS PARA EXPORTAÇÃO' : 'DADOS PRESERVADOS · REVISAR METADADOS'}
          </Text>
        </View>)}
      </Card>
      {!!formula.observations && <Callout title="OBSERVAÇÃO DA COR" tone="warning">{formula.observations}</Callout>}
      <Callout title="CONFERÊNCIA OBRIGATÓRIA" tone="info">Escolha a quantidade desejada em cada condição. O sistema recalcula as massas proporcionalmente a partir do padrão original do SkyMix.</Callout>
      {formula.variants.map((variant) => {
        const options = formulaQuantityOptions(formula.system, variant.condition);
        const selectedId = selectedQuantities[variant.formula_id] ?? options[0].id;
        const customValue = customQuantities[variant.formula_id] ?? '';
        const customUnit = customQuantityUnit(formula.system, variant.condition);
        const customMultiplier = customQuantityMultiplier(formula.system, variant.condition, customValue);
        const preset = options.find((option) => option.id === selectedId) ?? options[0];
        const selected = selectedId === 'custom'
          ? customMultiplier === null
            ? null
            : { id: 'custom', label: `${customValue.trim()} ${customUnit}`, multiplier: customMultiplier }
          : preset;
        return <View key={variant.formula_id} style={styles.variant}>
          <SectionHeader>{`${variant.condition} · VERSÃO ${variant.version}`}</SectionHeader>
          <Card tone="info">
            <Text style={styles.quantityTitle}>ESCOLHA A QUANTIDADE</Text>
            <View style={styles.quantityOptions}>
              {options.map((option) => <Pressable
                accessibilityRole="button"
                accessibilityState={{ selected: option.id === selectedId }}
                key={option.id}
                onPress={() => setSelectedQuantities((current) => ({
                  ...current,
                  [variant.formula_id]: option.id,
                }))}
                style={[styles.quantityOption, option.id === selectedId && styles.quantityOptionSelected]}
              >
                <Text style={[styles.quantityText, option.id === selectedId && styles.quantityTextSelected]}>{option.label}</Text>
              </Pressable>)}
            </View>
            <Text style={styles.customTitle}>OU DIGITE OUTRA QUANTIDADE</Text>
            <View style={styles.customRow}>
              <Field
                accessibilityLabel={`Quantidade personalizada em ${customUnit}`}
                keyboardType="decimal-pad"
                onChangeText={(value) => {
                  setCustomQuantities((current) => ({ ...current, [variant.formula_id]: value }));
                  setSelectedQuantities((current) => ({ ...current, [variant.formula_id]: 'custom' }));
                }}
                onFocus={() => setSelectedQuantities((current) => ({ ...current, [variant.formula_id]: 'custom' }))}
                placeholder={customUnit === 'ml' ? 'Ex.: 800' : 'Ex.: 1,5'}
                style={[styles.customField, selectedId === 'custom' && styles.customFieldSelected]}
                value={customValue}
              />
              <Text style={styles.customUnit}>{customUnit.toUpperCase()}</Text>
            </View>
            {selectedId === 'custom' && customMultiplier === null && <Text style={styles.customError}>Informe uma quantidade maior que zero.</Text>}
            {selected && <TechnicalRow label="Quantidade escolhida" value={selected.label} />}
            <TechnicalRow label="Condição" value={variant.condition} />
            <TechnicalRow label="Padrão de cálculo" value={options[0].label} />
            <TechnicalRow label="Atualização" value={variant.updated_at ? new Date(variant.updated_at).toLocaleDateString('pt-BR') : '—'} />
            {selected && variant.components.map((component) => <View key={`${variant.formula_id}-${component.position}`} style={styles.component}>
              <View style={styles.componentTop}>
                <Text style={styles.baseCode}>{component.base_code}</Text>
                <Text style={styles.weight}>{grams(scaleFormulaWeight(component.weight_g, selected.multiplier))}</Text>
              </View>
              {!!component.base_name && <Text style={styles.baseName}>{component.base_name}</Text>}
            </View>)}
            {selected && <View style={styles.total}>
              <Text style={styles.totalLabel}>TOTAL · {selected.label.toUpperCase()}</Text>
              <Text style={styles.totalWeight}>{grams(scaleFormulaWeight(variant.total_weight_g, selected.multiplier))}</Text>
            </View>}
          </Card>
        </View>;
      })}
    </>}
  </Screen>;
}

const styles = StyleSheet.create({
  modalBackdrop: { alignItems: 'center', backgroundColor: 'rgba(0, 0, 0, 0.78)', flex: 1, justifyContent: 'center', padding: spacing.md },
  modalCard: { backgroundColor: colors.surface, borderColor: colors.borderStrong, borderRadius: radius.lg, borderWidth: 1, gap: spacing.mdSm, maxWidth: 420, padding: spacing.lg, width: '100%' },
  modalEyebrow: { color: colors.technical, fontSize: 10, fontWeight: '900', letterSpacing: 1.2 },
  modalTitle: { color: colors.textPrimary, fontSize: 22, fontWeight: '900' },
  modalText: { color: colors.textSecondary, fontSize: 14, lineHeight: 21 },
  modalInfo: { backgroundColor: colors.technicalSoft, borderRadius: radius.sm, padding: spacing.mdSm },
  modalInfoText: { color: colors.textPrimary, fontSize: 12, fontWeight: '800', lineHeight: 18 },
  modalWarning: { backgroundColor: colors.warningSoft, borderRadius: radius.sm, padding: spacing.mdSm },
  modalWarningText: { color: colors.warning, fontSize: 12, fontWeight: '800', lineHeight: 18 },
  variant: { gap: spacing.sm },
  managementButtons: { gap: spacing.sm },
  datasetText: { color: colors.textSecondary, fontSize: 13, lineHeight: 19 },
  datasetWarning: { color: colors.warning, fontSize: 12, fontWeight: '800', lineHeight: 18 },
  captureNotice: { backgroundColor: colors.warningSoft, borderRadius: radius.sm, gap: spacing.sm, padding: spacing.mdSm },
  captureTitle: { color: colors.warning, fontSize: 12, fontWeight: '900', letterSpacing: 0.8, textAlign: 'center' },
  captureText: { color: colors.textPrimary, fontSize: 13, lineHeight: 19, textAlign: 'center' },
  saved: { color: colors.success, fontSize: 12, fontWeight: '900', textAlign: 'center' },
  readingRow: { borderTopColor: colors.border, borderTopWidth: 1, gap: 3, paddingTop: spacing.sm },
  readingTitle: { color: colors.textPrimary, fontSize: 11, fontWeight: '900' },
  readingDetail: { color: colors.textSecondary, fontSize: 10 },
  readingEligible: { color: colors.success, fontSize: 9, fontWeight: '900' },
  readingReview: { color: colors.warning, fontSize: 9, fontWeight: '900' },
  quantityTitle: { color: colors.textPrimary, fontSize: 12, fontWeight: '900', letterSpacing: 1 },
  quantityOptions: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  readingFormulaOptions: { gap: spacing.sm },
  readingFormulaOption: { backgroundColor: colors.surfaceElevated, borderColor: colors.borderStrong, borderRadius: radius.sm, borderWidth: 1, paddingHorizontal: 10, paddingVertical: 11 },
  quantityOption: { backgroundColor: colors.surfaceElevated, borderColor: colors.borderStrong, borderRadius: radius.sm, borderWidth: 1, minWidth: '30%', paddingHorizontal: 10, paddingVertical: 11 },
  quantityOptionSelected: { backgroundColor: colors.technicalSoft, borderColor: colors.technical, borderWidth: 2 },
  quantityText: { color: colors.textSecondary, fontSize: 12, fontWeight: '900', textAlign: 'center' },
  quantityTextSelected: { color: colors.white },
  customTitle: { color: colors.textSecondary, fontSize: 11, fontWeight: '900', letterSpacing: 0.8, marginTop: spacing.xs },
  customRow: { alignItems: 'center', flexDirection: 'row', gap: spacing.sm },
  customField: { flex: 1 },
  customFieldSelected: { borderColor: colors.technical, borderWidth: 2 },
  customUnit: { color: colors.technical, fontSize: 13, fontWeight: '900', minWidth: 62 },
  customError: { color: colors.warning, fontSize: 12, fontWeight: '800' },
  component: { borderBottomColor: colors.border, borderBottomWidth: 1, gap: 4, paddingBottom: spacing.mdSm },
  componentTop: { alignItems: 'baseline', flexDirection: 'row', justifyContent: 'space-between' },
  baseCode: { color: colors.textPrimary, fontSize: 17, fontWeight: '900' },
  weight: { color: colors.technical, fontSize: 19, fontWeight: '900' },
  baseName: { color: colors.textSecondary, fontSize: 12, lineHeight: 17 },
  total: { alignItems: 'baseline', backgroundColor: colors.surfaceElevated, flexDirection: 'row', justifyContent: 'space-between', marginTop: spacing.xs, padding: spacing.mdSm },
  totalLabel: { color: colors.textSecondary, fontSize: 12, fontWeight: '900', letterSpacing: 1 },
  totalWeight: { color: colors.success, fontSize: 21, fontWeight: '900' },
});
