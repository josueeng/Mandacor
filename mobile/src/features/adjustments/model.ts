import { Adjustment, AdjustmentComponent, AdjustmentCreatePayload, FinishType, PaintSystem } from '@/src/types/api';

export const VOLUME_PRESETS = ['450', '900', '3600'] as const;
export const APPLIED_WARNING = 'NÃO ADICIONE O PIGMENTO NOVAMENTE.';
export const OPERATOR_QUANTITY_NOTICE = 'Quantidade informada pelo operador. O MANDACOR não calculou esta dosagem.';

export interface AdjustmentForm {
  system: PaintSystem;
  finish: FinishType;
  volume: string;
  components: Array<{ pigmentCode: string; quantity: string }>;
  reason: string;
}

export function normalizePtBrDecimal(value: string): string | null {
  const normalized = value.trim().replace(',', '.');
  if (!/^\d+(?:\.\d+)?$/.test(normalized)) return null;
  if (!/[1-9]/.test(normalized)) return null;
  return normalized;
}

export function buildAdjustmentPayload(form: AdjustmentForm): AdjustmentCreatePayload | null {
  const volume = normalizePtBrDecimal(form.volume);
  const components: AdjustmentComponent[] = [];
  for (const item of form.components) {
    const quantity = normalizePtBrDecimal(item.quantity);
    const pigmentCode = item.pigmentCode.trim().toUpperCase();
    if (!quantity || !pigmentCode) return null;
    components.push({ pigment_code: pigmentCode, quantity_g: quantity });
  }
  if (!volume || !components.length || !form.reason.trim()) return null;
  return {
    system: form.system,
    finish: form.finish,
    volume_ml: volume,
    components,
    operator_reason: form.reason.trim(),
  };
}

export function canEditAdjustment(adjustment: Adjustment): boolean {
  return adjustment.lifecycle === 'PLANNED';
}

export function needsPhysicalConfirmation(adjustment: Adjustment): boolean {
  return adjustment.lifecycle === 'PLANNED';
}

export function preservePendingAfterTimeout(adjustment: Adjustment): Adjustment {
  if (adjustment.lifecycle !== 'APPLIED_WAITING_FOR_AFTER') {
    throw new Error('Only an applied pending adjustment can survive an AFTER timeout.');
  }
  return adjustment;
}

export function completedResultData(adjustment: Adjustment) {
  if (adjustment.lifecycle !== 'COMPLETED') return null;
  return {
    targetMeasurementId: adjustment.target_measurement_id,
    beforeMeasurementId: adjustment.before_measurement_id,
    afterMeasurementId: adjustment.after_measurement_id,
    observedResponse: adjustment.observed_response ?? [],
    outcomes: adjustment.outcomes ?? [],
    worstAngleBefore: adjustment.worst_angle_before,
    worstAngleAfter: adjustment.worst_angle_after,
  };
}
