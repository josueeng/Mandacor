import {
  COLOR_PLANE_LIMIT,
  colorPlaneScale,
  lightnessScale,
  numericTicks,
  projectColorPoint,
} from '@/src/components/ColorPlaneChart';

describe('ColorPlaneChart numeric scale', () => {
  it('creates symmetric numbers around target zero', () => {
    expect(numericTicks(2)).toEqual([-2, -1, 0, 1, 2]);
  });

  it('uses the professional base scale from -5 to +5 for ordinary deviations', () => {
    expect(colorPlaneScale(0.17, -0.24)).toBe(COLOR_PLANE_LIMIT);
    expect(projectColorPoint(0, 0, COLOR_PLANE_LIMIT)).toEqual({ left: 50, top: 50 });
  });

  it('expands to a readable symmetric scale instead of clipping large deviations', () => {
    const scale = colorPlaneScale(8, -12);
    expect(scale).toBe(20);
    expect(projectColorPoint(8, -12, scale)).toEqual({ left: 66.8, top: 75.2 });
  });

  it('keeps lightness magnitude comparable until a larger scale is necessary', () => {
    expect(lightnessScale(0.2)).toBe(5);
    expect(lightnessScale(-4.9)).toBe(5);
    expect(lightnessScale(5.1)).toBe(10);
  });
});
