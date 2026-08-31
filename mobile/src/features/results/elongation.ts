import { DeltaAngle, REQUIRED_ANGLES } from '@/src/types/api';

export const DEFAULT_ELONGATION_TOLERANCE = 2;

export interface ElongationAssessment {
  passes: boolean;
  variation: number;
  tolerance: number;
  lowestAngle: number;
  highestAngle: number;
}

/**
 * Compares the shape of the sample's lightness travel against the target.
 *
 * A uniform lightness offset at every angle changes the color, but not its
 * elongation. The peak-to-peak spread of ΔL* isolates how much the angular
 * lightness curve changed between target and sample.
 */
export function assessElongation(
  angles: readonly DeltaAngle[],
  tolerance = DEFAULT_ELONGATION_TOLERANCE,
): ElongationAssessment | null {
  if (!Number.isFinite(tolerance) || tolerance < 0) return null;

  const required = REQUIRED_ANGLES.map((angle) => angles.find((item) => item.angle === angle));
  if (required.some((item) => !item || !Number.isFinite(item.delta_l))) return null;

  const ordered = required as DeltaAngle[];
  const lowest = ordered.reduce((current, item) => item.delta_l < current.delta_l ? item : current);
  const highest = ordered.reduce((current, item) => item.delta_l > current.delta_l ? item : current);
  const variation = highest.delta_l - lowest.delta_l;

  return {
    passes: variation <= tolerance,
    variation,
    tolerance,
    lowestAngle: lowest.angle,
    highestAngle: highest.angle,
  };
}

export function configuredElongationTolerance(value: string | undefined): number {
  if (!value?.trim()) return DEFAULT_ELONGATION_TOLERANCE;
  const parsed = Number(value.replace(',', '.'));
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : DEFAULT_ELONGATION_TOLERANCE;
}
