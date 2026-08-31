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
