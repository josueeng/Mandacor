import { assessmentFindings, presentVerdict } from '@/src/features/adjustments/assessment';
import { AngleAssessment, TrialAssessment } from '@/src/types/api';

function angle(value: AngleAssessment['angle'], axes: AngleAssessment['axes']): AngleAssessment {
  return { angle: value, before_delta_e76: 1, after_delta_e76: 2, change: 'WORSENED', axes };
}

const assessment: TrialAssessment = {
  verdict: 'WORSENED',
  worst_delta_e_before: 1,
  worst_delta_e_after: 2,
  improved_angles: [],
  worsened_angles: [15, 45],
  overshoot_detected: true,
  wrong_direction_detected: true,
  delta_e_noise: 0.2,
  axis_noise: 0.15,
  angles: [
    angle(15, [
      { axis: 'L', before_delta: -1, after_delta: 1.5, change: 'WORSENED_OVERSHOOT', crossed_target: true },
      { axis: 'A', before_delta: 0, after_delta: 0, change: 'UNCHANGED', crossed_target: false },
    ]),
    angle(45, [
      { axis: 'B', before_delta: 0.5, after_delta: 1.2, change: 'WORSENED_WRONG_DIRECTION', crossed_target: false },
      { axis: 'A', before_delta: 2, after_delta: -0.3, change: 'IMPROVED', crossed_target: true },
    ]),
  ],
};

describe('trial assessment presentation', () => {
  test('shows a worsened trial as danger without operator input', () => {
    expect(presentVerdict('WORSENED')).toMatchObject({ title: 'FICOU PIOR', tone: 'danger' });
    expect(presentVerdict('IMPROVED').tone).toBe('success');
  });

  test('explains only the axes that worsened, distinguishing overshoot from wrong direction', () => {
    const findings = assessmentFindings(assessment).map((item) => item.text);
    expect(findings).toHaveLength(2);
    expect(findings[0]).toBe('15° L*: passou do ponto (era -1.00, ficou +1.50). Dose excessiva para este eixo.');
    expect(findings[1]).toBe('45° b*: foi na direção contrária ao alvo (era +0.50, ficou +1.20).');
  });
});
