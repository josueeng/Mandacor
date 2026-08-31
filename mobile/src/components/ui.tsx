import { PropsWithChildren, ReactNode } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TextInputProps,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { formatSigned, orderAngles } from '@/src/presentation/format';
import { colors, radius, spacing, typography } from '@/src/theme/tokens';
import { DeltaAngle, LabAngle } from '@/src/types/api';

export function Screen({ children }: PropsWithChildren) {
  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <ScrollView contentContainerStyle={styles.screen} keyboardShouldPersistTaps="handled">
        {children}
      </ScrollView>
    </SafeAreaView>
  );
}

type Tone = 'default' | 'info' | 'success' | 'warning' | 'danger';

export function Card({ children, tone = 'default' }: PropsWithChildren<{ tone?: Tone }>) {
  return <View style={[styles.card, tone !== 'default' && styles[`${tone}Card`]]}>{children}</View>;
}

export function SectionHeader({ children }: PropsWithChildren) {
  return (
    <View style={styles.sectionWrap}>
      <View style={styles.sectionAccent} />
      <Text style={styles.section}>{children}</Text>
    </View>
  );
}

export function ScreenHeader({
  eyebrow,
  title,
  subtitle,
}: {
  eyebrow?: string;
  title: string;
  subtitle?: string;
}) {
  return (
    <View style={styles.screenHeader}>
      {eyebrow && <Text style={styles.eyebrow}>{eyebrow}</Text>}
      <Text style={styles.screenTitle}>{title}</Text>
      {subtitle && <Text style={styles.screenSubtitle}>{subtitle}</Text>}
    </View>
  );
}

export function Callout({
  title,
  children,
  tone = 'info',
}: PropsWithChildren<{ title: string; tone?: Exclude<Tone, 'default'> }>) {
  return (
    <View style={[styles.callout, styles[`${tone}Callout`]]}>
      <Text style={[styles.calloutTitle, styles[`${tone}CalloutTitle`]]}>{title}</Text>
      <Text style={styles.calloutText}>{children}</Text>
    </View>
  );
}

interface ButtonProps {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  loading?: boolean;
  secondary?: boolean;
  warning?: boolean;
}

export function ActionButton({ label, onPress, disabled, loading, secondary, warning }: ButtonProps) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      disabled={disabled || loading}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        secondary && styles.buttonSecondary,
        warning && styles.buttonWarning,
        (pressed || disabled || loading) && styles.buttonMuted,
      ]}
    >
      {loading ? <ActivityIndicator color={colors.textPrimary} /> : <Text style={styles.buttonText}>{label}</Text>}
    </Pressable>
  );
}

export function Field(props: TextInputProps) {
  return (
    <TextInput
      {...props}
      placeholderTextColor={colors.textSecondary}
      style={[styles.field, props.style]}
      autoCapitalize="none"
      autoCorrect={false}
    />
  );
}

export function StatusBadge({ online, label }: { online: boolean; label: string }) {
  return (
    <View style={[styles.badge, online ? styles.badgeOnline : styles.badgeAttention]}>
      <Text style={{ color: online ? colors.success : colors.warning }}>●</Text>
      <Text style={styles.badgeText}>{label}</Text>
    </View>
  );
}

export function ErrorNotice({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <View accessibilityRole="alert" style={styles.errorBox}>
      <Text style={styles.errorText}>⚠ {message}</Text>
    </View>
  );
}

export function EmptyState({ children }: PropsWithChildren) {
  return (
    <View style={styles.emptyState}>
      <Text style={styles.emptyIcon}>○</Text>
      <Text style={styles.emptyText}>{children}</Text>
    </View>
  );
}

export function LabCards({ angles }: { angles: LabAngle[] }) {
  return (
    <View style={styles.labTable}>
      <View style={[styles.labRow, styles.labHeader]}>
        <Text style={[styles.labCell, styles.labAngleCell, styles.labHeaderText]}>ÂNGULO</Text>
        <Text style={[styles.labCell, styles.labHeaderText]}>L*</Text>
        <Text style={[styles.labCell, styles.labHeaderText]}>a*</Text>
        <Text style={[styles.labCell, styles.labHeaderText]}>b*</Text>
      </View>
      {orderAngles(angles).map((item) => (
        <View key={item.angle} style={styles.labRow}>
          <Text style={[styles.labCell, styles.labAngleCell]}>{item.angle}°</Text>
          <Text style={styles.labCell}>{item.l.toFixed(2)}</Text>
          <Text style={styles.labCell}>{formatSigned(item.a, 2)}</Text>
          <Text style={styles.labCell}>{formatSigned(item.b, 2)}</Text>
        </View>
      ))}
    </View>
  );
}

export function DeltaCards({ angles }: { angles: DeltaAngle[] }) {
  return (
    <View style={styles.angleGrid}>
      {orderAngles(angles).map((item) => (
        <Card key={item.angle}>
          <Text style={styles.angleTitle}>{item.angle}°</Text>
          <TechnicalRow label="ΔL" value={formatSigned(item.delta_l)} />
          <TechnicalRow label="Δa" value={formatSigned(item.delta_a)} />
          <TechnicalRow label="Δb" value={formatSigned(item.delta_b)} />
          <TechnicalRow label="ΔE76" value={item.delta_e76.toFixed(3)} />
        </Card>
      ))}
    </View>
  );
}

export function TechnicalRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.technical}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  screen: {
    alignSelf: 'center',
    gap: 14,
    maxWidth: 480,
    paddingHorizontal: 16,
    paddingTop: 18,
    paddingBottom: 110,
    width: '100%',
  },
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radius.md,
    borderWidth: 1,
    padding: spacing.md,
    gap: spacing.mdSm,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.16,
    shadowRadius: 12,
    elevation: 2,
  },
  infoCard: { borderLeftColor: colors.technical, borderLeftWidth: 3 },
  successCard: { borderLeftColor: colors.success, borderLeftWidth: 3 },
  warningCard: { borderLeftColor: colors.warning, borderLeftWidth: 3 },
  dangerCard: { borderLeftColor: colors.danger, borderLeftWidth: 3 },
  sectionWrap: { alignItems: 'center', flexDirection: 'row', gap: 9, marginTop: spacing.sm },
  sectionAccent: { backgroundColor: colors.action, borderRadius: 2, height: 16, width: 3 },
  section: {
    color: colors.textPrimary,
    fontSize: 13,
    fontWeight: '900',
    letterSpacing: 1.1,
  },
  screenHeader: { gap: 5, marginBottom: spacing.xs },
  eyebrow: { color: colors.action, fontSize: 11, fontWeight: '900', letterSpacing: 1.8 },
  screenTitle: { color: colors.textPrimary, fontSize: 30, fontWeight: '900', letterSpacing: -0.5 },
  screenSubtitle: { color: colors.textSecondary, fontSize: 14, lineHeight: 20, maxWidth: 390 },
  callout: { borderLeftWidth: 3, borderRadius: radius.sm, gap: 5, padding: spacing.md },
  infoCallout: { backgroundColor: colors.technicalSoft, borderLeftColor: colors.technical },
  successCallout: { backgroundColor: colors.successSoft, borderLeftColor: colors.success },
  warningCallout: { backgroundColor: colors.warningSoft, borderLeftColor: colors.warning },
  dangerCallout: { backgroundColor: colors.dangerSoft, borderLeftColor: colors.danger },
  calloutTitle: { fontSize: 12, fontWeight: '900', letterSpacing: 0.8 },
  infoCalloutTitle: { color: colors.technical },
  successCalloutTitle: { color: colors.success },
  warningCalloutTitle: { color: colors.warning },
  dangerCalloutTitle: { color: colors.danger },
  calloutText: { color: colors.textPrimary, fontSize: 14, lineHeight: 21 },
  button: {
    minHeight: 52,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.action,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.md,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.18,
    shadowRadius: 7,
    elevation: 2,
  },
  buttonSecondary: { backgroundColor: colors.surfaceElevated, borderWidth: 1, borderColor: colors.border },
  buttonWarning: { backgroundColor: '#5C4512', borderWidth: 1, borderColor: colors.warning },
  buttonMuted: { opacity: 0.5, transform: [{ scale: 0.99 }] },
  buttonText: { color: colors.textPrimary, fontSize: 13, fontWeight: '900', letterSpacing: 0.7 },
  field: {
    minHeight: 52,
    backgroundColor: colors.surfaceElevated,
    borderColor: colors.border,
    borderRadius: radius.sm,
    borderWidth: 1,
    color: colors.textPrimary,
    fontSize: 15,
    paddingHorizontal: spacing.md,
  },
  badge: {
    alignSelf: 'flex-start',
    alignItems: 'center',
    borderRadius: 999,
    borderWidth: 1,
    flexDirection: 'row',
    gap: spacing.sm,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  badgeOnline: { backgroundColor: colors.successSoft, borderColor: colors.success },
  badgeAttention: { backgroundColor: colors.warningSoft, borderColor: colors.warning },
  badgeText: { color: colors.textPrimary, fontSize: 12, fontWeight: '800' },
  errorBox: { backgroundColor: colors.dangerSoft, borderColor: colors.danger, borderLeftWidth: 3, borderRadius: radius.sm, padding: spacing.md },
  errorText: { color: colors.danger, fontSize: 15, fontWeight: '700' },
  muted: { color: colors.textSecondary, fontSize: 13, lineHeight: 20 },
  emptyState: { alignItems: 'center', backgroundColor: colors.surfaceSubtle, borderColor: colors.border, borderRadius: radius.md, borderStyle: 'dashed', borderWidth: 1, gap: spacing.sm, padding: spacing.lg },
  emptyIcon: { color: colors.textMuted, fontSize: 28 },
  emptyText: { color: colors.textSecondary, fontSize: 14, lineHeight: 21, textAlign: 'center' },
  angleGrid: { gap: spacing.sm },
  angleTitle: { color: colors.textPrimary, fontSize: 16, fontWeight: '900' },
  row: { alignItems: 'flex-start', borderBottomColor: '#202831', borderBottomWidth: 1, flexDirection: 'row', gap: spacing.md, justifyContent: 'space-between', minHeight: 30, paddingBottom: 7 },
  rowLabel: { color: colors.textSecondary, flexShrink: 1, fontSize: 12, lineHeight: 18 },
  technical: { color: colors.technical, flexShrink: 1, fontFamily: 'SpaceMono', fontSize: 12, lineHeight: 18, textAlign: 'right' },
  labTable: { borderColor: colors.border, borderRadius: radius.md, borderWidth: 1, overflow: 'hidden' },
  labRow: { backgroundColor: colors.surface, borderBottomColor: colors.border, borderBottomWidth: 1, flexDirection: 'row', minHeight: 42 },
  labHeader: { backgroundColor: colors.surfaceElevated },
  labCell: { color: colors.technical, flex: 1, fontFamily: 'SpaceMono', fontSize: 11, paddingHorizontal: 7, paddingVertical: 12, textAlign: 'right' },
  labAngleCell: { color: colors.textPrimary, fontFamily: undefined, fontWeight: '900', textAlign: 'left' },
  labHeaderText: { color: colors.textSecondary, fontFamily: undefined, fontSize: 9, fontWeight: '900' },
});

export const uiStyles = styles;
