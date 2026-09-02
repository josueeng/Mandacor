import { FormulaSystem } from '@/src/types/api';

export interface FormulaQuantityOption {
  id: string;
  label: string;
  multiplier: number;
}

const QUART_OPTIONS: FormulaQuantityOption[] = [
  { id: 'quart-1', label: '1 Quarto', multiplier: 1 },
  { id: 'quart-half', label: '1/2 Quarto', multiplier: 0.5 },
  { id: 'quart-2', label: '2 Quartos', multiplier: 2 },
  { id: 'quart-3', label: '3 Quartos', multiplier: 3 },
  { id: 'quart-4', label: '4 Quartos', multiplier: 4 },
];

const PU_DILUTED_OPTIONS: FormulaQuantityOption[] = [
  { id: 'pu-diluted-675', label: '675 ml', multiplier: 1 },
  { id: 'pu-diluted-337', label: '337 ml', multiplier: 0.5 },
  { id: 'pu-diluted-1350', label: '1350 ml', multiplier: 2 },
  { id: 'pu-diluted-2025', label: '2025 ml', multiplier: 3 },
  { id: 'pu-diluted-2700', label: '2700 ml', multiplier: 4 },
];

export function formulaQuantityOptions(
  system: FormulaSystem,
  condition: string,
): FormulaQuantityOption[] {
  return system === 'PU' && condition.toUpperCase() === 'DILUIDO'
    ? PU_DILUTED_OPTIONS
    : QUART_OPTIONS;
}

export function scaleFormulaWeight(weight: string, multiplier: number): string {
  const numeric = Number(weight);
  if (!Number.isFinite(numeric) || numeric < 0 || multiplier <= 0) {
    throw new Error('Invalid formula weight or multiplier.');
  }
  const rounded = Math.round((numeric * multiplier + Number.EPSILON) * 10000) / 10000;
  return rounded.toFixed(4).replace(/\.0+$/, '').replace(/(\.\d*?)0+$/, '$1');
}

export function customQuantityMultiplier(
  system: FormulaSystem,
  condition: string,
  input: string,
): number | null {
  const normalized = input.trim().replace(',', '.');
  if (!/^\d+(?:\.\d+)?$/.test(normalized)) return null;
  const quantity = Number(normalized);
  if (!Number.isFinite(quantity) || quantity <= 0) return null;
  return system === 'PU' && condition.toUpperCase() === 'DILUIDO'
    ? quantity / 675
    : quantity;
}

export function customQuantityUnit(system: FormulaSystem, condition: string): 'ml' | 'Quartos' {
  return system === 'PU' && condition.toUpperCase() === 'DILUIDO' ? 'ml' : 'Quartos';
}
