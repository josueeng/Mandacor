import {
  assessElongation,
  configuredElongationTolerance,
  DEFAULT_ELONGATION_TOLERANCE,
} from '@/src/features/results/elongation';
import { DeltaAngle, REQUIRED_ANGLES } from '@/src/types/api';

function deltas(values: readonly number[]): DeltaAngle[] {
  return REQUIRED_ANGLES.map((angle, index) => ({
    angle,
    delta_l: values[index],
    delta_a: 0,
    delta_b: 0,
    delta_e76: Math.abs(values[index]),
  }));
}

describe('assessElongation', () => {
  it('approves the reference readings supplied by the colorist', () => {
    const result = assessElongation(deltas([0.57, 0.19, -0.29, -0.83, -1.12]));

    expect(result).toEqual({
      passes: true,
      variation: 1.69,
      tolerance: 2,
      lowestAngle: 105,
      highestAngle: 15,
    });
  });

  it('ignores a uniform lightness offset because it does not change travel shape', () => {
    expect(assessElongation(deltas([1.5, 1.5, 1.5, 1.5, 1.5]))?.variation).toBe(0);
  });

  it('rejects a curve whose peak-to-peak lightness variation exceeds tolerance', () => {
    const result = assessElongation(deltas([1.2, 0.5, 0, -0.4, -1.1]));

    expect(result?.passes).toBe(false);
    expect(result?.variation).toBeCloseTo(2.3);
  });

  it('requires all five angles', () => {
    expect(assessElongation(deltas([0, 0, 0, 0, 0]).slice(1))).toBeNull();
  });
});

describe('configuredElongationTolerance', () => {
  it('accepts decimal comma and falls back for invalid values', () => {
    expect(configuredElongationTolerance('2,5')).toBe(2.5);
    expect(configuredElongationTolerance('invalid')).toBe(DEFAULT_ELONGATION_TOLERANCE);
  });
});
