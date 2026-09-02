import { router, useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';

import { MandacorApiClient } from '@/src/api/client';
import { friendlyError } from '@/src/api/errors';
import { ActionButton, Card, EmptyState, ErrorNotice, Field, Screen, ScreenHeader, TechnicalRow } from '@/src/components/ui';
import { useMandacor } from '@/src/state/AppContext';
import { colors, radius, spacing } from '@/src/theme/tokens';
import { FormulaProductSummary, FormulaSearchFilters, FormulaSpectralMatch, FormulaSystem } from '@/src/types/api';

const FILTERS: Array<{ value?: FormulaSystem; label: string }> = [
  { label: 'TODAS' },
  { value: 'POLIESTER', label: 'POLIÉSTER' },
  { value: 'PU', label: 'PU' },
  { value: 'LACA', label: 'LACA' },
  { value: 'ESMALTE_SINTETICO', label: 'SINTÉTICO' },
  { value: 'EPOXI', label: 'EPÓXI' },
];

const ACTIVE_CAPTURE_STATES = new Set(['PREPARED', 'WAITING']);

function isSpectralMatch(item: FormulaProductSummary): item is FormulaSpectralMatch {
  return 'compatibility' in item;
}

export default function FormulasScreen() {
  const app = useMandacor();
  const client = useMemo(() => new MandacorApiClient(app.baseUrl), [app.baseUrl]);
  const [query, setQuery] = useState('');
  const [system, setSystem] = useState<FormulaSystem | undefined>();
  const [filters, setFilters] = useState<FormulaSearchFilters>({});
  const [showMoreFilters, setShowMoreFilters] = useState(false);
  const [items, setItems] = useState<FormulaProductSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showSpectralModal, setShowSpectralModal] = useState(false);
  const [spectralCaptureRequested, setSpectralCaptureRequested] = useState(false);
  const [spectralLoading, setSpectralLoading] = useState(false);
  const [spectralItems, setSpectralItems] = useState<FormulaSpectralMatch[] | null>(null);
  const [totalCompared, setTotalCompared] = useState(0);
  const spectralRole = useRef<'target' | 'sample'>('sample');
  const spectralBaselineId = useRef<number | null>(null);

  const openFormula = useCallback((code: string) => {
    router.push(`../formula?code=${encodeURIComponent(code)}`);
  }, []);

  const load = useCallback(async (offset = 0) => {
    setLoading(true);
    try {
      const result = await client.searchFormulas(query, system, 30, offset, filters);
      setItems((current) => offset > 0 ? [...current, ...result.items] : result.items);
      setTotal(result.total);
      setError(null);
    } catch (caught) {
      setError(friendlyError(caught));
    } finally {
      setLoading(false);
    }
  }, [client, filters, query, system]);

  const runTextSearch = useCallback(() => {
    setSpectralItems(null);
    setTotalCompared(0);
    void load(0);
  }, [load]);

  const operation = app.activeOperation;
  const spectralCaptureActive = Boolean(
    spectralCaptureRequested
    && operation?.session_id === app.currentSession?.session_id
    && operation?.type === spectralRole.current.toUpperCase()
    && Boolean(operation && ACTIVE_CAPTURE_STATES.has(operation.status)),
  );

  const startSpectralCapture = () => {
    const session = app.currentSession;
    if (!session || !app.instrument.connected) return;
    const role = session.target ? 'sample' : 'target';
    spectralRole.current = role;
    spectralBaselineId.current = (role === 'sample' ? session.sample : session.target)?.measurement_id ?? null;
    setShowSpectralModal(false);
    setSpectralItems(null);
    setTotalCompared(0);
    setError(null);
    app.clearError();
    setSpectralCaptureRequested(true);
    void app.prepareCapture(role);
  };

  useEffect(() => {
    if (!spectralCaptureRequested || !app.currentSession) return;
    const role = spectralRole.current;
    const measurement = role === 'sample' ? app.currentSession.sample : app.currentSession.target;
    if (!measurement || measurement.measurement_id === spectralBaselineId.current) return;
    setSpectralCaptureRequested(false);
    setSpectralLoading(true);
    void client.formulaSpectralMatches(app.currentSession.session_id, role)
      .then((result) => {
        setSpectralItems(result.items);
        setTotalCompared(result.total_compared);
        setError(null);
      })
      .catch((caught) => setError(friendlyError(caught)))
      .finally(() => setSpectralLoading(false));
  }, [app.currentSession, client, spectralCaptureRequested]);

  useFocusEffect(useCallback(() => {
    void load(0);
  }, [load]));

  const displayedItems: FormulaProductSummary[] = spectralItems ?? items;

  return <Screen>
    <Modal
      animationType="fade"
      onRequestClose={() => setShowSpectralModal(false)}
      transparent
      visible={showSpectralModal}
    >
      <View style={styles.modalBackdrop}>
        <View accessibilityRole="alert" style={styles.modalCard}>
          <Text style={styles.modalEyebrow}>BUSCA PELO DATASET</Text>
          <Text style={styles.modalTitle}>Buscar pela leitura do espectro?</Text>
          <Text style={styles.modalText}>Uma nova leitura será comparada com todas as cores que já possuem dados do espectrofotômetro.</Text>
          {!app.instrument.connected ? <>
            <View style={styles.modalWarning}>
              <Text style={styles.modalWarningText}>O espectrofotômetro está desconectado.</Text>
            </View>
            <ActionButton label="IR PARA CONEXÃO" onPress={() => { setShowSpectralModal(false); router.push('/'); }} />
          </> : !app.currentSession ? <>
            <View style={styles.modalInfo}>
              <Text style={styles.modalInfoText}>Crie uma sessão de medição para preparar a leitura usada na busca.</Text>
            </View>
            <ActionButton label="CRIAR SESSÃO DE LEITURA" loading={app.busy} onPress={() => void app.createComparison()} />
          </> : <>
            <View style={styles.modalInfo}>
              <Text style={styles.modalInfoText}>Depois de iniciar, faça a leitura no aparelho. Uma leitura antiga não será usada automaticamente.</Text>
            </View>
            <ActionButton label="INICIAR E AGUARDAR LEITURA" disabled={app.busy} onPress={startSpectralCapture} />
          </>}
          <ActionButton label="CANCELAR" secondary onPress={() => setShowSpectralModal(false)} />
        </View>
      </View>
    </Modal>
    <ScreenHeader
      eyebrow="CATÁLOGO SKYMIX"
      title="Fórmulas de tinta"
      subtitle="Busque pelo código comercial, cor ou use os filtros adicionais."
    />
    <ActionButton label="+ CADASTRAR NOVA TINTA" onPress={() => router.push('../formula-editor')} />
    <Field
      value={query}
      onChangeText={setQuery}
      onSubmitEditing={runTextSearch}
      placeholder="Ex.: vermelho fogo ou 210-03121"
      returnKeyType="search"
    />
    <View style={styles.filters}>
      {FILTERS.map((filter) => <Pressable
        key={filter.label}
        onPress={() => { setSpectralItems(null); setSystem(filter.value); }}
        style={[styles.filter, system === filter.value && styles.filterActive]}
      >
        <Text style={[styles.filterText, system === filter.value && styles.filterTextActive]}>{filter.label}</Text>
      </Pressable>)}
    </View>
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ expanded: showMoreFilters }}
      onPress={() => setShowMoreFilters((current) => !current)}
      style={styles.moreFiltersButton}
    >
      <Text style={styles.moreFiltersText}>{showMoreFilters ? '− OCULTAR OUTROS FILTROS' : '+ PESQUISAR POR OUTROS FILTROS'}</Text>
    </Pressable>
    {showMoreFilters && <Card>
      <Text style={styles.fieldLabel}>MONTADORA</Text>
      <Field
        value={filters.manufacturer ?? ''}
        onChangeText={(manufacturer) => setFilters((current) => ({ ...current, manufacturer }))}
        onSubmitEditing={runTextSearch}
        placeholder="Ex.: Fiat, VW, Chevrolet"
        returnKeyType="search"
      />
      <Text style={styles.fieldLabel}>ANO</Text>
      <Field
        value={filters.year ?? ''}
        onChangeText={(year) => setFilters((current) => ({ ...current, year }))}
        onSubmitEditing={runTextSearch}
        placeholder="Ex.: 2019"
        keyboardType="number-pad"
        returnKeyType="search"
      />
      <Text style={styles.fieldLabel}>ASPECTO</Text>
      <Field
        value={filters.finish ?? ''}
        onChangeText={(finish) => setFilters((current) => ({ ...current, finish }))}
        onSubmitEditing={runTextSearch}
        placeholder="Ex.: lisa, metálico, perolizado"
        returnKeyType="search"
      />
      <Text style={styles.fieldLabel}>CÓDIGO UNIVERSAL</Text>
      <Field
        value={filters.universalCode ?? ''}
        onChangeText={(universalCode) => setFilters((current) => ({ ...current, universalCode }))}
        onSubmitEditing={runTextSearch}
        placeholder="Ex.: 178"
        returnKeyType="search"
      />
      <Pressable onPress={() => setFilters({})} style={styles.clearFilters}>
        <Text style={styles.clearFiltersText}>LIMPAR FILTROS ADICIONAIS</Text>
      </Pressable>
    </Card>}
    <ActionButton label="BUSCAR FÓRMULAS" onPress={runTextSearch} loading={loading && !items.length} />
    <ActionButton
      label="BUSCAR COR POR LEITURA DO ESPECTRO"
      secondary
      disabled={app.busy || spectralCaptureActive || spectralLoading}
      onPress={() => { app.clearError(); setShowSpectralModal(true); }}
    />
    {spectralCaptureActive && <Card tone="warning">
      <Text style={styles.captureTitle}>AGUARDANDO LEITURA PARA BUSCA</Text>
      <Text style={styles.captureText}>Faça agora uma nova leitura no espectrofotômetro. Em seguida, todas as cores do dataset serão comparadas automaticamente.</Text>
      <ActionButton label="CANCELAR ESPERA" warning disabled={app.busy} onPress={() => void app.cancelCapture()} />
    </Card>}
    {spectralLoading && <Card tone="info"><Text style={styles.captureTitle}>COMPARANDO TODAS AS CORES DO DATASET…</Text></Card>}
    <ErrorNotice message={error ?? app.errorMessage} />
    {spectralItems !== null ? <>
      <View style={styles.spectralHeader}>
        <Text style={styles.counter}>{totalCompared.toLocaleString('pt-BR')} CORES DO DATASET COMPARADAS</Text>
        <ActionButton label="VOLTAR À BUSCA POR TEXTO" secondary onPress={() => setSpectralItems(null)} />
      </View>
    </> : <Text style={styles.counter}>{total.toLocaleString('pt-BR')} CORES ENCONTRADAS</Text>}
    {displayedItems.map((item) => <Card key={item.code} tone={item.reading_count === 0 ? 'danger' : 'info'}>
      <Pressable accessibilityRole="button" onPress={() => openFormula(item.code)} style={styles.formulaLink}>
          <View style={styles.titleRow}>
            <Text style={styles.title}>{item.description}</Text>
            {isSpectralMatch(item)
              ? <View style={styles.compatibilityBadge}><Text style={styles.compatibilityValue}>{item.compatibility.toFixed(1)}%</Text><Text style={styles.compatibilityLabel}>COMPATÍVEL</Text></View>
              : <Text style={styles.arrow}>›</Text>}
          </View>
          {isSpectralMatch(item) && <TechnicalRow label="Distância multiângulo ΔE" value={item.delta_e.toFixed(2)} />}
          <TechnicalRow label="Código" value={item.display_code} />
          <TechnicalRow label="Sistema" value={`${item.system_label} · ${item.paint_line}`} />
          {!!item.manufacturer && <TechnicalRow label="Montadora" value={item.manufacturer} />}
          {!!item.year && <TechnicalRow label="Ano" value={item.year} />}
          {!!item.universal_code && <TechnicalRow label="Cód. universal" value={item.universal_code} />}
          {item.origin === 'USER' && <TechnicalRow label="Origem" value="CADASTRO DO USUÁRIO" />}
          {item.reading_count > 0 && <TechnicalRow label="Dataset" value={`${item.reading_count} leitura${item.reading_count === 1 ? '' : 's'}`} />}
          {item.reading_count === 0 && <TechnicalRow label="Dataset" value="SEM LEITURA DO ESPECTRO" />}
          <TechnicalRow label="Opções" value={`${item.formula_count} fórmula${item.formula_count === 1 ? '' : 's'}`} />
      </Pressable>
      {item.reading_count === 0 && <ActionButton
        label="COLETAR LEITURA DO ESPECTRO"
        onPress={() => openFormula(item.code)}
      />}
    </Card>)}
    {!loading && !spectralLoading && !displayedItems.length && <EmptyState>{spectralItems === null ? 'Nenhuma fórmula encontrada. Tente outro termo ou sistema.' : 'O dataset ainda não possui cores com leituras para comparar.'}</EmptyState>}
    {spectralItems === null && items.length < total && <ActionButton label="CARREGAR MAIS" secondary loading={loading} onPress={() => void load(items.length)} />}
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
  captureTitle: { color: colors.warning, fontSize: 12, fontWeight: '900', letterSpacing: 0.8, textAlign: 'center' },
  captureText: { color: colors.textPrimary, fontSize: 13, lineHeight: 19, textAlign: 'center' },
  spectralHeader: { gap: spacing.sm },
  compatibilityBadge: { alignItems: 'center', backgroundColor: colors.successSoft, borderColor: colors.success, borderRadius: radius.sm, borderWidth: 1, minWidth: 84, paddingHorizontal: spacing.sm, paddingVertical: 6 },
  compatibilityValue: { color: colors.success, fontSize: 17, fontWeight: '900' },
  compatibilityLabel: { color: colors.textSecondary, fontSize: 8, fontWeight: '900', letterSpacing: 0.5 },
  filters: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  filter: { backgroundColor: colors.surfaceElevated, borderColor: colors.border, borderRadius: radius.sm, borderWidth: 1, paddingHorizontal: 11, paddingVertical: 9 },
  filterActive: { backgroundColor: colors.technicalSoft, borderColor: colors.technical },
  filterText: { color: colors.textSecondary, fontSize: 10, fontWeight: '900', letterSpacing: 0.5 },
  filterTextActive: { color: colors.technical },
  moreFiltersButton: { alignItems: 'center', borderColor: colors.borderStrong, borderRadius: radius.sm, borderWidth: 1, padding: 11 },
  moreFiltersText: { color: colors.technical, fontSize: 11, fontWeight: '900', letterSpacing: 0.6 },
  fieldLabel: { color: colors.textSecondary, fontSize: 10, fontWeight: '900', letterSpacing: 0.8, marginTop: spacing.xs },
  clearFilters: { alignItems: 'center', padding: spacing.sm },
  clearFiltersText: { color: colors.warning, fontSize: 10, fontWeight: '900', letterSpacing: 0.6 },
  counter: { color: colors.textMuted, fontSize: 10, fontWeight: '900', letterSpacing: 1.1, marginTop: spacing.sm },
  formulaLink: { gap: spacing.mdSm },
  titleRow: { alignItems: 'flex-start', flexDirection: 'row', gap: spacing.sm, justifyContent: 'space-between' },
  title: { color: colors.textPrimary, flex: 1, fontSize: 16, fontWeight: '900' },
  arrow: { color: colors.action, fontSize: 28, lineHeight: 22 },
});
