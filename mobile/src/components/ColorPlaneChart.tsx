import { Fragment } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing } from '@/src/theme/tokens';
import { LabAngle, REQUIRED_ANGLES, RequiredAngle } from '@/src/types/api';

interface ColorPlaneChartProps {
  selectedAngle: RequiredAngle;
  onSelectAngle: (angle: RequiredAngle) => void;
  target: LabAngle;
  sample: LabAngle;
}

const PLOT_RANGE = 42;
const TICK_POSITIONS = [8, 29, 50, 71, 92] as const;
export const COLOR_PLANE_LIMIT = 5;
const SCALE_STEPS = [5, 10, 20, 40, 80, 160, 320] as const;

export function numericTicks(scale: number): number[] {
  return [-scale, -scale / 2, 0, scale / 2, scale];
}

function formatTick(value: number): string {
  if (value === 0) return '0';
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}`;
}

function adaptiveScale(...values: number[]): number {
  const magnitude = Math.max(0, ...values.filter(Number.isFinite).map(Math.abs));
  return SCALE_STEPS.find((step) => step >= magnitude) ?? Math.ceil(magnitude / 100) * 100;
}

export function colorPlaneScale(deltaA: number, deltaB: number): number {
  return adaptiveScale(deltaA, deltaB);
}

export function lightnessScale(deltaL: number): number {
  return adaptiveScale(deltaL);
}

export function projectColorPoint(a: number, b: number, scale: number) {
  const boundedA = Math.max(-scale, Math.min(scale, a));
  const boundedB = Math.max(-scale, Math.min(scale, b));
  return {
    left: 50 + (boundedA / scale) * PLOT_RANGE,
    top: 50 - (boundedB / scale) * PLOT_RANGE,
  };
}

export function ColorPlaneChart({
  selectedAngle,
  onSelectAngle,
  target,
  sample,
}: ColorPlaneChartProps) {
  const deltaA = sample.a - target.a;
  const deltaB = sample.b - target.b;
  const deltaL = sample.l - target.l;
  const scale = colorPlaneScale(deltaA, deltaB);
  const samplePoint = projectColorPoint(deltaA, deltaB, scale);

  return (
    <View style={styles.container}>
      <View accessibilityRole="tablist" style={styles.angleRow}>
        {REQUIRED_ANGLES.map((angle) => {
          const selected = angle === selectedAngle;
          return (
            <Pressable
              accessibilityLabel={`Mostrar ângulo de ${angle} graus`}
              accessibilityRole="tab"
              accessibilityState={{ selected }}
              key={angle}
              onPress={() => onSelectAngle(angle)}
              style={[styles.angleButton, selected && styles.angleButtonSelected]}
            >
              <Text style={[styles.angleText, selected && styles.angleTextSelected]}>{angle}°</Text>
            </Pressable>
          );
        })}
      </View>

      <View
        accessibilityLabel={`Desvio da amostra no ângulo ${selectedAngle} graus. Delta a ${deltaA.toFixed(2)}, delta b ${deltaB.toFixed(2)}.`}
        style={styles.plot}
      >
        <View style={[styles.quadrant, styles.yellowGreen]} />
        <View style={[styles.quadrant, styles.yellowRed]} />
        <View style={[styles.quadrant, styles.blueGreen]} />
        <View style={[styles.quadrant, styles.blueRed]} />
        <View style={styles.horizontalAxis} />
        <View style={styles.verticalAxis} />
        <CartesianNumbers scale={scale} />
        <View style={styles.origin} />
        <Text style={styles.originLabel}>ALVO · 0</Text>

        <Text style={[styles.axisLabel, styles.yellowLabel]}>Δb* · MAIS AMARELA</Text>
        <Text style={[styles.axisLabel, styles.blueLabel]}>Δb* · MAIS AZUL</Text>
        <Text style={[styles.axisLabel, styles.greenLabel]}>Δa* · MAIS VERDE</Text>
        <Text style={[styles.axisLabel, styles.redLabel]}>Δa* · MAIS VERMELHA</Text>

        <PlotPoint
          label="T"
          name="Amostra"
          left={samplePoint.left}
          top={samplePoint.top}
          style={styles.samplePoint}
        />
      </View>

      <LightnessScale delta={deltaL} angle={selectedAngle} />

      <View style={styles.legend}>
        <LegendItem color={colors.action} label="T · AMOSTRA" />
        <Text style={styles.scale}>ESCALA ±{scale.toFixed(2)}</Text>
      </View>
    </View>
  );
}

function CartesianNumbers({ scale }: { scale: number }) {
  const ticks = numericTicks(scale);

  return (
    <>
      {ticks.map((value) => {
        if (value === 0) return null;
        const position = 50 + (value / scale) * PLOT_RANGE;
        return (
          <Fragment key={`x-${value}`}>
            <View style={[styles.xTick, { left: `${position}%` }]} />
            <Text style={[
              styles.axisNumber,
              styles.xTickLabel,
              value < 0 ? styles.greenNumber : styles.redNumber,
              { left: `${position}%` },
            ]}>
              {formatTick(value)}
            </Text>
          </Fragment>
        );
      })}
      {ticks.map((value) => {
        if (value === 0) return null;
        const position = 50 - (value / scale) * PLOT_RANGE;
        return (
          <Fragment key={`y-${value}`}>
            <View style={[styles.yTick, { top: `${position}%` }]} />
            <Text style={[
              styles.axisNumber,
              styles.yTickLabel,
              value < 0 ? styles.blueNumber : styles.yellowNumber,
              { top: `${position}%` },
            ]}>
              {formatTick(value)}
            </Text>
          </Fragment>
        );
      })}
    </>
  );
}

function LightnessScale({
  delta,
  angle,
}: {
  delta: number;
  angle: RequiredAngle;
}) {
  const scale = lightnessScale(delta);
  const samplePosition = 50 + (delta / scale) * PLOT_RANGE;
  const ticks = numericTicks(scale);

  return (
    <View
      accessibilityLabel={`Desvio de luminosidade da amostra no ângulo ${angle} graus. Delta L ${delta.toFixed(2)}.`}
      style={styles.lightness}
    >
      <View style={styles.lightnessHeader}>
        <Text style={styles.lightnessTitle}>L* · LUMINOSIDADE</Text>
        <Text style={styles.lightnessDelta}>
          ΔL {delta >= 0 ? '+' : ''}{delta.toFixed(3)}
        </Text>
      </View>
      <View style={styles.lightnessTrackArea}>
        <View style={styles.lightnessTrack} />
        {ticks.map((value, index) => (
          <Fragment key={TICK_POSITIONS[index]}>
            <View style={[styles.lightnessNumericTick, { left: `${index * 25}%` }]} />
            <Text style={[
              styles.lightnessTickLabel,
              value === 0 && styles.lightnessZeroLabel,
              { left: `${index * 25}%` },
            ]}>
              {formatTick(value)}
            </Text>
          </Fragment>
        ))}
        <LightnessMarker label="T" value={delta} position={samplePosition} style={styles.sampleLightnessMarker} top={36} />
      </View>
      <View style={styles.lightnessLabels}>
        <Text style={styles.lightnessEnd}>MAIS ESCURA</Text>
        <Text style={styles.lightnessEnd}>MAIS CLARA</Text>
      </View>
    </View>
  );
}

function LightnessMarker({
  label,
  value,
  position,
  style,
  top,
}: {
  label: string;
  value: number;
  position: number;
  style: object;
  top: number;
}) {
  return (
    <View style={[styles.lightnessMarker, style, { left: `${position}%`, top }]}>
      <Text style={styles.lightnessMarkerLabel}>{label}</Text>
      <Text style={styles.lightnessMarkerValue}>{value >= 0 ? '+' : ''}{value.toFixed(2)}</Text>
    </View>
  );
}

function PlotPoint({
  label,
  name,
  left,
  top,
  style,
}: {
  label: string;
  name: string;
  left: number;
  top: number;
  style: object;
}) {
  return (
    <View
      accessibilityLabel={name}
      style={[
        styles.point,
        style,
        { left: `${left}%`, top: `${top}%` },
      ]}
    >
      <Text style={styles.pointText}>{label}</Text>
    </View>
  );
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <View style={styles.legendItem}>
      <View style={[styles.legendDot, { backgroundColor: color }]} />
      <Text style={styles.legendText}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: spacing.sm },
  angleRow: { flexDirection: 'row', gap: 6 },
  angleButton: {
    alignItems: 'center',
    backgroundColor: colors.surfaceElevated,
    borderColor: colors.border,
    borderRadius: radius.sm,
    borderWidth: 1,
    flex: 1,
    minHeight: 42,
    justifyContent: 'center',
  },
  angleButtonSelected: { backgroundColor: '#13334A', borderColor: colors.technical },
  angleText: { color: colors.textSecondary, fontSize: 13, fontWeight: '800' },
  angleTextSelected: { color: colors.textPrimary },
  plot: {
    aspectRatio: 1,
    backgroundColor: '#0D1116',
    borderColor: colors.border,
    borderRadius: radius.sm,
    borderWidth: 1,
    overflow: 'hidden',
    position: 'relative',
    width: '100%',
  },
  quadrant: { height: '50%', position: 'absolute', width: '50%' },
  yellowGreen: { backgroundColor: 'rgba(245, 185, 66, 0.035)', left: 0, top: 0 },
  yellowRed: { backgroundColor: 'rgba(229, 57, 53, 0.04)', right: 0, top: 0 },
  blueGreen: { backgroundColor: 'rgba(54, 194, 117, 0.035)', bottom: 0, left: 0 },
  blueRed: { backgroundColor: 'rgba(61, 169, 252, 0.04)', bottom: 0, right: 0 },
  horizontalAxis: {
    backgroundColor: '#657180',
    height: 1,
    left: '8%',
    position: 'absolute',
    right: '8%',
    top: '50%',
  },
  verticalAxis: {
    backgroundColor: '#657180',
    bottom: '8%',
    left: '50%',
    position: 'absolute',
    top: '8%',
    width: 1,
  },
  xTick: {
    backgroundColor: '#657180',
    height: 7,
    marginLeft: -1,
    marginTop: -3,
    position: 'absolute',
    top: '50%',
    width: 1,
  },
  axisNumber: {
    backgroundColor: '#0D1116',
    borderRadius: 3,
    fontFamily: 'SpaceMono',
    fontSize: 8,
    fontWeight: '900',
    lineHeight: 12,
    position: 'absolute',
    textAlign: 'center',
    width: 24,
  },
  xTickLabel: {
    marginLeft: -12,
    marginTop: -6,
    top: '50%',
  },
  yTick: {
    backgroundColor: '#657180',
    height: 1,
    left: '50%',
    marginLeft: -3,
    marginTop: -1,
    position: 'absolute',
    width: 7,
  },
  yTickLabel: {
    left: '50%',
    marginLeft: -12,
    marginTop: -6,
  },
  greenNumber: { color: '#52C685' },
  redNumber: { color: '#F06A67' },
  blueNumber: { color: '#5CAEF5' },
  yellowNumber: { color: '#E9C45B' },
  origin: {
    backgroundColor: colors.technical,
    borderRadius: 4,
    height: 7,
    left: '50%',
    marginLeft: -3,
    marginTop: -3,
    position: 'absolute',
    top: '50%',
    width: 7,
  },
  originLabel: {
    color: colors.technical,
    fontSize: 9,
    fontWeight: '900',
    left: '50%',
    marginLeft: 7,
    marginTop: 6,
    position: 'absolute',
    top: '50%',
  },
  axisLabel: { fontSize: 10, fontWeight: '900', position: 'absolute' },
  yellowLabel: { color: '#E9C45B', left: '50%', top: 8, transform: [{ translateX: -55 }] },
  blueLabel: { bottom: 8, color: '#5CAEF5', left: '50%', transform: [{ translateX: -43 }] },
  greenLabel: { color: '#52C685', left: 8, top: '44%' },
  redLabel: { color: '#F06A67', right: 8, top: '44%' },
  point: {
    alignItems: 'center',
    borderColor: colors.textPrimary,
    borderRadius: 12,
    borderWidth: 2,
    height: 24,
    justifyContent: 'center',
    marginLeft: -12,
    marginTop: -12,
    position: 'absolute',
    width: 24,
  },
  samplePoint: {
    backgroundColor: colors.action,
    borderColor: colors.textPrimary,
    height: 18,
    marginLeft: -9,
    marginTop: -9,
    width: 18,
  },
  pointText: { color: '#FFFFFF', fontSize: 10, fontWeight: '900' },
  lightness: {
    backgroundColor: colors.surfaceElevated,
    borderRadius: radius.sm,
    gap: 4,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm,
  },
  lightnessHeader: { alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between' },
  lightnessTitle: { color: colors.textPrimary, fontSize: 10, fontWeight: '900', letterSpacing: 0.5 },
  lightnessDelta: { color: colors.technical, fontFamily: 'SpaceMono', fontSize: 10 },
  lightnessTrackArea: { height: 64, marginHorizontal: 24, position: 'relative' },
  lightnessTrack: {
    backgroundColor: '#AEB6C0',
    height: 2,
    left: 0,
    position: 'absolute',
    right: 0,
    top: 28,
  },
  lightnessNumericTick: {
    backgroundColor: colors.textSecondary,
    height: 8,
    marginLeft: -1,
    position: 'absolute',
    top: 25,
    width: 2,
  },
  lightnessMarker: {
    alignItems: 'center',
    borderRadius: 4,
    flexDirection: 'row',
    gap: 3,
    marginLeft: -22,
    paddingHorizontal: 4,
    position: 'absolute',
    width: 52,
  },
  sampleLightnessMarker: { backgroundColor: '#421B1B' },
  lightnessTickLabel: {
    backgroundColor: colors.surfaceElevated,
    borderRadius: 3,
    color: colors.textSecondary,
    fontFamily: 'SpaceMono',
    fontSize: 8,
    fontWeight: '800',
    lineHeight: 12,
    marginLeft: -22,
    position: 'absolute',
    textAlign: 'center',
    top: 22,
    width: 44,
  },
  lightnessZeroLabel: { color: colors.technical, fontWeight: '900' },
  lightnessMarkerLabel: { color: colors.textPrimary, fontSize: 9, fontWeight: '900' },
  lightnessMarkerValue: { color: colors.textPrimary, fontFamily: 'SpaceMono', fontSize: 9 },
  lightnessLabels: { flexDirection: 'row', justifyContent: 'space-between' },
  lightnessEnd: { color: colors.textSecondary, fontSize: 9, fontWeight: '700' },
  legend: { alignItems: 'center', flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  legendItem: { alignItems: 'center', flexDirection: 'row', gap: 5 },
  legendDot: { borderRadius: 5, height: 9, width: 9 },
  legendText: { color: colors.textSecondary, fontSize: 10, fontWeight: '800' },
  scale: { color: colors.textSecondary, fontFamily: 'SpaceMono', fontSize: 9, marginLeft: 'auto' },
});
