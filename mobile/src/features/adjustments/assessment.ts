import { formatSigned } from '@/src/presentation/format';
import { AxisAssessment, TrialAssessment, TrialVerdict } from '@/src/types/api';

type Tone = 'success' | 'danger' | 'warning' | 'info';

const VERDICTS: Record<TrialVerdict, { title: string; description: string; tone: Tone }> = {
  IMPROVED: {
    title: 'MELHOROU',
    description: 'A amostra ficou mais próxima do alvo, sem piora relevante em nenhum ângulo.',
    tone: 'success',
  },
  WORSENED: {
    title: 'FICOU PIOR',
    description: 'A amostra se afastou do alvo segundo o instrumento. Reavalie antes de adicionar mais pigmento.',
    tone: 'danger',
  },
  MIXED: {
    title: 'RESULTADO MISTO',
    description: 'Alguns ângulos melhoraram e outros pioraram. O pigmento ajuda numa região e atrapalha em outra.',
    tone: 'warning',
  },
  UNCHANGED: {
    title: 'SEM MUDANÇA SIGNIFICATIVA',
    description: 'A variação ficou dentro do ruído de medição/aplicação. A dose pode ter sido pequena demais.',
    tone: 'info',
  },
};

const AXIS_LABEL: Record<AxisAssessment['axis'], string> = { L: 'L*', A: 'a*', B: 'b*' };

export interface AssessmentFinding {
  key: string;
  text: string;
}

export function presentVerdict(verdict: TrialVerdict) {
  return VERDICTS[verdict];
}

function range(values: number[]): string {
  const min = Math.min(...values);
  const max = Math.max(...values);
  return min === max ? formatSigned(min, 2) : `${formatSigned(min, 2)} a ${formatSigned(max, 2)}`;
}

/**
 * Lists every axis that worsened, grouping angles with the same problem, so the operator
 * sees why the instrument judged it worse.
 */
export function assessmentFindings(assessment: TrialAssessment): AssessmentFinding[] {
  const groups = new Map<string, { axis: AxisAssessment['axis']; change: AxisAssessment['change']; angles: number[]; before: number[]; after: number[] }>();
  for (const angle of assessment.angles) {
    for (const axis of angle.axes) {
      if (axis.change !== 'WORSENED_OVERSHOOT' && axis.change !== 'WORSENED_WRONG_DIRECTION') continue;
      const key = `${axis.axis}-${axis.change}`;
      const group = groups.get(key) ?? { axis: axis.axis, change: axis.change, angles: [], before: [], after: [] };
      group.angles.push(angle.angle);
      group.before.push(axis.before_delta);
      group.after.push(axis.after_delta);
      groups.set(key, group);
    }
  }
  return [...groups.entries()].map(([key, group]) => {
    const label = `${group.angles.map((angle) => `${angle}°`).join(', ')} ${AXIS_LABEL[group.axis]}`;
    const values = `era ${range(group.before)}, ficou ${range(group.after)}`;
    const text = group.change === 'WORSENED_OVERSHOOT'
      ? `${label}: passou do ponto (${values}). Dose excessiva para este eixo.`
      : `${label}: foi na direção contrária ao alvo (${values}).`;
    return { key, text };
  });
}

export const OPERATOR_DISAGREEMENT_NOTICE =
  'Seu feedback visual contradiz a análise do instrumento. Confira iluminação, ângulo de observação e a chapinha antes de salvar.';
