import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { MandacorApiClient } from '@/src/api/client';
import { friendlyError } from '@/src/api/errors';
import { ActionButton, Card, ErrorNotice, Field, Screen, ScreenHeader, SectionHeader } from '@/src/components/ui';
import { useMandacor } from '@/src/state/AppContext';
import { colors, radius, spacing } from '@/src/theme/tokens';
import { FormulaSystem, FormulaUpsertPayload, FormulaVariantPayload } from '@/src/types/api';

const SYSTEMS: Array<{ value: FormulaSystem; label: string; prefix: string }> = [
  { value: 'POLIESTER', label: 'POLIÉSTER', prefix: '210' },
  { value: 'PU', label: 'PU', prefix: '610' },
  { value: 'LACA', label: 'LACA', prefix: '510' },
  { value: 'ESMALTE_SINTETICO', label: 'SINTÉTICO', prefix: '410' },
  { value: 'EPOXI', label: 'EPÓXI', prefix: 'E' },
];

const emptyVariant = (): FormulaVariantPayload => ({
  condition: 'DILUIDO', package: '1 Quarto', version: 1,
  components: [{ base_code: '', base_name: '', weight_g: '' }],
});

const emptyForm = (): FormulaUpsertPayload => ({
  code: '', description: '', year: '', universal_code: '', nuance: '',
  manufacturer: '', observations: '', system: 'POLIESTER', finish_label: 'LISA',
  variants: [emptyVariant()],
});

export default function FormulaEditorScreen() {
  const parameters = useLocalSearchParams<{ code?: string | string[] }>();
  const editCode = Array.isArray(parameters.code) ? parameters.code[0] : parameters.code;
  const { baseUrl } = useMandacor();
  const client = useMemo(() => new MandacorApiClient(baseUrl), [baseUrl]);
  const [form, setForm] = useState<FormulaUpsertPayload>(emptyForm);
  const [loading, setLoading] = useState(Boolean(editCode));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!editCode) return;
    client.getFormula(editCode).then((product) => setForm({
      code: product.display_code,
      description: product.description,
      year: product.year,
      universal_code: product.universal_code,
      nuance: product.nuance,
      manufacturer: product.manufacturer,
      observations: product.observations,
      system: product.system,
      finish_label: product.finish_label || 'LISA',
      variants: product.variants.map((variant) => ({
        condition: variant.condition,
        package: variant.package || '1 Quarto',
        version: variant.version,
        components: variant.components.map((component) => ({
          base_code: component.base_code,
          base_name: component.base_name,
          weight_g: component.weight_g.replace('.', ','),
        })),
      })),
    })).catch((caught) => setError(friendlyError(caught))).finally(() => setLoading(false));
  }, [client, editCode]);

  const setValue = <K extends keyof FormulaUpsertPayload>(key: K, value: FormulaUpsertPayload[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const updateVariant = (index: number, update: Partial<FormulaVariantPayload>) => {
    setForm((current) => ({
      ...current,
      variants: current.variants.map((variant, position) => position === index ? { ...variant, ...update } : variant),
    }));
  };

  const updateComponent = (variantIndex: number, componentIndex: number, key: 'base_code' | 'base_name' | 'weight_g', value: string) => {
    const components = form.variants[variantIndex].components.map((component, position) => (
      position === componentIndex ? { ...component, [key]: value } : component
    ));
    updateVariant(variantIndex, { components });
  };

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload = {
        ...form,
        code: form.code.trim(),
        description: form.description.trim(),
        variants: form.variants.map((variant) => ({
          ...variant,
          components: variant.components.map((component) => ({
            ...component,
            weight_g: component.weight_g.trim().replace(',', '.'),
          })),
        })),
      };
      const saved = editCode
        ? await client.updateFormula(editCode, payload)
        : await client.createFormula(payload);
      router.replace({ pathname: '/formula', params: { code: saved.code } });
    } catch (caught) {
      setError(friendlyError(caught));
    } finally {
      setSaving(false);
    }
  };

  return <Screen>
    <ActionButton label="‹ VOLTAR" secondary onPress={() => router.back()} />
    <ScreenHeader
      eyebrow={editCode ? 'EDITAR TINTA' : 'NOVA TINTA'}
      title={editCode ? form.description || 'Carregando...' : 'Cadastrar fórmula'}
      subtitle="Informe os dados da cor e as massas da fórmula padrão."
    />
    <ErrorNotice message={error} />
    {!loading && <>
      <SectionHeader>IDENTIFICAÇÃO</SectionHeader>
      <Card>
        <Text style={styles.label}>SISTEMA</Text>
        <View style={styles.choices}>{SYSTEMS.map((item) => <Pressable
          key={item.value}
          onPress={() => setValue('system', item.value)}
          style={[styles.choice, form.system === item.value && styles.choiceActive]}
        ><Text style={[styles.choiceText, form.system === item.value && styles.choiceTextActive]}>{item.label}</Text></Pressable>)}</View>
        <Text style={styles.label}>CÓDIGO COMERCIAL</Text>
        <Field
          editable={!editCode}
          value={form.code}
          onChangeText={(value) => setValue('code', value)}
          placeholder={`Ex.: ${SYSTEMS.find((item) => item.value === form.system)?.prefix}-00000`}
        />
        <Text style={styles.label}>PRODUTO / COR</Text>
        <Field value={form.description} onChangeText={(value) => setValue('description', value)} placeholder="Nome da tinta" />
        <Text style={styles.label}>MONTADORA</Text>
        <Field value={form.manufacturer} onChangeText={(value) => setValue('manufacturer', value)} placeholder="Ex.: VW" />
        <Text style={styles.label}>CÓDIGO UNIVERSAL</Text>
        <Field value={form.universal_code} onChangeText={(value) => setValue('universal_code', value)} placeholder="Ex.: LB9A / B4B4" />
        <Text style={styles.label}>ANO</Text>
        <Field value={form.year} onChangeText={(value) => setValue('year', value)} placeholder="Ex.: 1992-2026" />
        <Text style={styles.label}>ASPECTO / SUBGRUPO</Text>
        <Field value={form.finish_label} onChangeText={(value) => setValue('finish_label', value)} placeholder="LISA, METALICO, PEROLIZADO..." />
        <Text style={styles.label}>NUANCE</Text>
        <Field value={form.nuance} onChangeText={(value) => setValue('nuance', value)} placeholder="Opcional" />
        <Text style={styles.label}>OBSERVAÇÕES</Text>
        <Field multiline value={form.observations} onChangeText={(value) => setValue('observations', value)} placeholder="Opcional" />
      </Card>

      {form.variants.map((variant, variantIndex) => <View key={`variant-${variantIndex}`} style={styles.section}>
        <SectionHeader>FÓRMULA {variantIndex + 1}</SectionHeader>
        <Card tone="info">
          <Text style={styles.label}>CONDIÇÃO</Text>
          <View style={styles.choices}>{['DILUIDO', 'CONCENTRADO'].map((condition) => <Pressable
            key={condition}
            onPress={() => updateVariant(variantIndex, { condition })}
            style={[styles.choice, variant.condition === condition && styles.choiceActive]}
          ><Text style={[styles.choiceText, variant.condition === condition && styles.choiceTextActive]}>{condition}</Text></Pressable>)}</View>
          <Text style={styles.label}>EMBALAGEM PADRÃO</Text>
          <Field value={variant.package} onChangeText={(value) => updateVariant(variantIndex, { package: value })} placeholder="1 Quarto ou 675 ml" />
          {variant.components.map((component, componentIndex) => <View key={`component-${componentIndex}`} style={styles.component}>
            <Text style={styles.componentTitle}>BASE {componentIndex + 1}</Text>
            <Field value={component.base_code} onChangeText={(value) => updateComponent(variantIndex, componentIndex, 'base_code', value)} placeholder="Código da base, ex.: BP240" />
            <Field value={component.base_name} onChangeText={(value) => updateComponent(variantIndex, componentIndex, 'base_name', value)} placeholder="Descrição da base" />
            <Field keyboardType="decimal-pad" value={component.weight_g} onChangeText={(value) => updateComponent(variantIndex, componentIndex, 'weight_g', value)} placeholder="Peso em gramas" />
            {variant.components.length > 1 && <ActionButton label="REMOVER ESTA BASE" warning onPress={() => updateVariant(variantIndex, { components: variant.components.filter((_, index) => index !== componentIndex) })} />}
          </View>)}
          <ActionButton label="+ ADICIONAR BASE" secondary onPress={() => updateVariant(variantIndex, { components: [...variant.components, { base_code: '', base_name: '', weight_g: '' }] })} />
          {form.variants.length > 1 && <ActionButton label="REMOVER ESTA FÓRMULA" warning onPress={() => setForm((current) => ({ ...current, variants: current.variants.filter((_, index) => index !== variantIndex) }))} />}
        </Card>
      </View>)}
      <ActionButton label="+ ADICIONAR OUTRA CONDIÇÃO" secondary onPress={() => setForm((current) => ({ ...current, variants: [...current.variants, emptyVariant()] }))} />
      <ActionButton label={editCode ? 'SALVAR ALTERAÇÕES' : 'CADASTRAR TINTA'} loading={saving} onPress={() => void save()} />
    </>}
  </Screen>;
}

const styles = StyleSheet.create({
  section: { gap: spacing.sm },
  label: { color: colors.textSecondary, fontSize: 10, fontWeight: '900', letterSpacing: 0.8, marginTop: spacing.xs },
  choices: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  choice: { borderColor: colors.borderStrong, borderRadius: radius.sm, borderWidth: 1, paddingHorizontal: 11, paddingVertical: 9 },
  choiceActive: { backgroundColor: colors.technicalSoft, borderColor: colors.technical },
  choiceText: { color: colors.textSecondary, fontSize: 10, fontWeight: '900' },
  choiceTextActive: { color: colors.white },
  component: { borderColor: colors.border, borderRadius: radius.sm, borderWidth: 1, gap: spacing.sm, padding: spacing.mdSm },
  componentTitle: { color: colors.technical, fontSize: 11, fontWeight: '900', letterSpacing: 0.8 },
});
