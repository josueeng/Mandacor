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

function describeAxis(angle: number, axis: AxisAssessment): string | null {
  const values = `era ${formatSigned(axis.before_delta, 2)}, ficou ${formatSigned(axis.after_delta, 2)}`;
  const label = `${angle}° ${AXIS_LABEL[axis.axis]}`;
  if (axis.change === 'WORSENED_OVERSHOOT') {
    return `${label}: passou do ponto (${values}). Dose excessiva para este eixo.`;
  }
  if (axis.change === 'WORSENED_WRONG_DIRECTION') {
    return `${label}: foi na direção contrária ao alvo (${values}).`;
  }
  return null;
}

/** Lists every axis that worsened, so the operator sees why the instrument judged it worse. */
export function assessmentFindings(assessment: TrialAssessment): AssessmentFinding[] {
  return assessment.angles.flatMap((angle) =>
    angle.axes.flatMap((axis) => {
      const text = describeAxis(angle.angle, axis);
      return text ? [{ key: `${angle.angle}-${axis.axis}`, text }] : [];
    }));
}

export const OPERATOR_DISAGREEMENT_NOTICE =
  'Seu feedback visual contradiz a análise do instrumento. Confira iluminação, ângulo de observação e a chapinha antes de salvar.';
