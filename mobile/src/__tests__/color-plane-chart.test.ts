import {
  COLOR_PLANE_LIMIT,
  colorPlaneScale,
  numericTicks,
  projectColorPoint,
} from '@/src/components/ColorPlaneChart';

describe('ColorPlaneChart numeric scale', () => {
  it('creates symmetric numbers around target zero', () => {
    expect(numericTicks(2)).toEqual([-2, -1, 0, 1, 2]);
  });

  it('uses the fixed professional scale from -5 to +5', () => {
    expect(colorPlaneScale(0.17, -0.24)).toBe(COLOR_PLANE_LIMIT);
    expect(colorPlaneScale(8, -12)).toBe(COLOR_PLANE_LIMIT);
    expect(projectColorPoint(0, 0, COLOR_PLANE_LIMIT)).toEqual({ left: 50, top: 50 });
  });

  it('keeps out-of-range samples visible at the chart border', () => {
    expect(projectColorPoint(8, -12, COLOR_PLANE_LIMIT)).toEqual({ left: 92, top: 92 });
  });
});
