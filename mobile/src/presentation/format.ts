import { REQUIRED_ANGLES } from '@/src/types/api';

const directionPtBr: Record<string, string> = {
  DARKER: 'MAIS ESCURA',
  LIGHTER: 'MAIS CLARA',
  REDDER: 'MAIS VERMELHA',
  GREENER: 'MAIS VERDE',
  YELLOWER: 'MAIS AMARELA',
  BLUER: 'MAIS AZUL',
  NEUTRAL: 'SEM DESVIO',
  MIXED: 'MISTO',
};

const actionPtBr: Record<string, string> = {
  LIGHTEN: 'CLAREAR',
  DARKEN: 'ESCURECER',
  MOVE_GREENER: 'ESVERDEAR',
  MOVE_REDDER: 'AVERMELHAR',
  MOVE_BLUER: 'AZULAR',
  MOVE_YELLOWER: 'AMARELAR',
  MIXED: 'MISTO',
  NONE: 'SEM AÇÃO',
};

const statePtBr: Record<string, string> = {
  ONLINE: 'CONECTADO',
  OFFLINE: 'DESCONECTADO',
  UNKNOWN: 'NÃO VERIFICADO',
  WAITING_FOR_TARGET: 'AGUARDANDO COR ALVO',
  TARGET_CAPTURED: 'ALVO CAPTURADO',
  WAITING_FOR_SAMPLE: 'AGUARDANDO AMOSTRA',
  READY_FOR_COMPARISON: 'PRONTA PARA COMPARAR',
  PREPARED: 'PREPARADA',
  WAITING: 'AGUARDANDO LEITURA',
  COMPLETED: 'CONCLUÍDA',
  TIMED_OUT: 'TEMPO ESGOTADO',
  CANCELLED: 'CANCELADA',
  FAILED: 'FALHOU',
  PLANNED: 'PLANEJADO',
  APPLIED_WAITING_FOR_AFTER: 'APLICADO · AGUARDANDO AFTER',
  ABANDONED_AFTER_APPLICATION: 'ABANDONADO APÓS APLICAÇÃO',
};

export const presentDirection = (value: string): string => directionPtBr[value] ?? value;
export const presentAction = (value: string): string => actionPtBr[value] ?? value;
export const presentState = (value: string): string => statePtBr[value] ?? value.replaceAll('_', ' ');

export function orderAngles<T extends { angle: number }>(angles: readonly T[]): T[] {
  return REQUIRED_ANGLES.flatMap((required) => {
    const found = angles.find((item) => item.angle === required);
    return found ? [found] : [];
  });
}

export function formatSigned(value: number, digits = 3): string {
  if (Object.is(value, -0) || value === 0) return (0).toFixed(digits);
  return `${value > 0 ? '+' : ''}${value.toFixed(digits)}`;
}

/** Decimal with PT-BR comma, for sentences shown to the operator. */
export function formatDecimal(value: number, digits = 2): string {
  return Math.abs(value).toFixed(digits).replace('.', ',');
}

const axisNamePtBr: Record<string, string> = {
  L: 'Claro / escuro (L*)',
  A: 'Vermelho / verde (a*)',
  B: 'Amarelo / azul (b*)',
  TIE: 'Empate entre eixos',
};

/** Words for a positive and a negative difference (amostra − alvo) on each axis. */
const axisSidePtBr: Record<string, [string, string]> = {
  L: ['mais clara', 'mais escura'],
  A: ['mais vermelha', 'mais verde'],
  B: ['mais amarela', 'mais azul'],
};

export const presentAxis = (axis: string): string => axisNamePtBr[axis.toUpperCase()] ?? axis;

/** Describes a sample − target difference, e.g. "1,20 mais escura que o alvo". */
export function describeDeviation(axis: string, value: number, digits = 2): string {
  const sides = axisSidePtBr[axis.toUpperCase()];
  if (!sides || value === 0) return 'igual ao alvo';
  return `${formatDecimal(value, digits)} ${value > 0 ? sides[0] : sides[1]} que o alvo`;
}

/** Describes a change between two readings (depois − antes), e.g. "ficou 0,50 mais clara". */
export function describeChange(axis: string, value: number, digits = 2): string {
  const sides = axisSidePtBr[axis.toUpperCase()];
  if (!sides || Math.abs(value) < 0.5 * 10 ** -digits) return 'não mudou';
  return `ficou ${formatDecimal(value, digits)} ${value > 0 ? sides[0] : sides[1]}`;
}

const labelsPtBr: Record<string, string> = {
  POLYESTER_BASECOAT: 'POLIÉSTER (BASE)',
  PU: 'PU',
  SOLID: 'SÓLIDA',
  METALLIC: 'METÁLICA',
  PEARL: 'PEROLIZADA',
  BETTER: 'MELHOR',
  WORSE: 'PIOR',
  SAME: 'IGUAL',
  IN_PROGRESS: 'EM ANDAMENTO',
  ACCEPTED: 'APROVADO',
  REJECTED: 'REPROVADO',
  IMPROVED: 'MELHOROU',
  WORSENED: 'PIOROU',
  UNCHANGED: 'SEM MUDANÇA',
  RECOMMENDED_CANDIDATE: 'RECOMENDADO',
  CONDITIONAL: 'COM RESSALVAS',
  CONFLICTING: 'CONFLITANTE',
  CONTRAINDICATED: 'CONTRAINDICADO',
  INSUFFICIENT_KNOWLEDGE: 'SEM DADOS SUFICIENTES',
  MILKY: 'deixa leitoso',
  DIRTYING: 'suja a cor',
  DARKENING: 'escurece',
  STRONG_DARKENING: 'escurece muito',
  LIGHTENING: 'clareia',
  FLOP_OPENING: 'abre o flop',
  FRONT_DIRTYING: 'suja a frente',
  PARTICLE_CHANGE: 'altera a partícula',
  HUE_COUPLING: 'muda mais de um tom junto',
  EFFECT_CHANGE: 'altera o efeito',
  FRONT: 'FRENTE',
  MID: '45°',
  FLOP: 'FLOP',
};

/** Operator-facing label for backend enum names; "UNKNOWN" depends on context, so it is passed in. */
export function presentLabel(value: string, unknown = 'NÃO INFORMADO'): string {
  if (value === 'UNKNOWN') return unknown;
  return labelsPtBr[value] ?? value.replaceAll('_', ' ');
}
