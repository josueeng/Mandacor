import { describeDeviation, formatDecimal, presentAxis } from '@/src/presentation/format';
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

export interface AssessmentFinding {
  key: string;
  text: string;
}

export function presentVerdict(verdict: TrialVerdict) {
  return VERDICTS[verdict];
}

/** "1,20 mais clara que o alvo", or "entre 1,80 e 2,00 mais escura que o alvo" for several angles. */
function describeRange(axis: string, values: number[]): string {
  const sorted = [...values].sort((left, right) => Math.abs(left) - Math.abs(right));
  const smallest = sorted[0];
  const largest = sorted[sorted.length - 1];
  if (formatDecimal(smallest) === formatDecimal(largest)) return describeDeviation(axis, largest);
  return `entre ${formatDecimal(smallest)} e ${describeDeviation(axis, largest)}`;
}

/**
 * Lists every axis that worsened, grouping angles with the same problem, so the operator
 * sees why the instrument judged it worse.
 */
export function assessmentFindings(assessment: TrialAssessment): AssessmentFinding[] {
  type Group = { axis: AxisAssessment['axis']; change: AxisAssessment['change']; angles: number[]; before: number[]; after: number[] };
  const groups = new Map<string, Group>();
  for (const angle of assessment.angles) {
    for (const axis of angle.axes) {
      if (axis.change !== 'WORSENED_OVERSHOOT' && axis.change !== 'WORSENED_WRONG_DIRECTION') continue;
      // Sides are part of the key so one sentence never mixes "mais clara" with "mais escura".
      const key = `${axis.axis}-${axis.change}-${Math.sign(axis.before_delta)}-${Math.sign(axis.after_delta)}`;
      const group = groups.get(key) ?? { axis: axis.axis, change: axis.change, angles: [], before: [], after: [] };
      group.angles.push(angle.angle);
      group.before.push(axis.before_delta);
      group.after.push(axis.after_delta);
      groups.set(key, group);
    }
  }
  return [...groups.entries()].map(([key, group]) => {
    const where = `${presentAxis(group.axis)} em ${group.angles.map((angle) => `${angle}°`).join(', ')}`;
    const values = `estava ${describeRange(group.axis, group.before)} e ficou ${describeRange(group.axis, group.after)}`;
    const text = group.change === 'WORSENED_OVERSHOOT'
      ? `${where}: passou do ponto. A amostra ${values}. A dose foi maior que o necessário.`
      : `${where}: foi para o lado errado. A amostra ${values}.`;
    return { key, text };
  });
}

export const OPERATOR_DISAGREEMENT_NOTICE =
  'Sua avaliação visual contradiz a medição do instrumento. Confira iluminação, ângulo de observação e a chapinha antes de salvar.';

export const COLOR_DIFFERENCE_HELP =
  'Diferença de cor (ΔE) é a distância entre a amostra e o alvo, somando claro/escuro, vermelho/verde e amarelo/azul. 0 = idêntica ao alvo; quanto maior, mais diferente.';
