import {
  APPLIED_WARNING,
  buildAdjustmentPayload,
  canEditAdjustment,
  completedResultData,
  needsPhysicalConfirmation,
  normalizePtBrDecimal,
  OPERATOR_QUANTITY_NOTICE,
  preservePendingAfterTimeout,
  VOLUME_PRESETS,
} from '@/src/features/adjustments/model';
import { Adjustment } from '@/src/types/api';

const adjustment = (lifecycle: Adjustment['lifecycle']) => ({ lifecycle } as Adjustment);

describe('adjustment form model', () => {
  test('accepts PT-BR decimal comma without calculating a dose', () => {
    expect(normalizePtBrDecimal('0,10')).toBe('0.10');
    expect(normalizePtBrDecimal('450,0')).toBe('450.0');
  });

  test('decimal_input_remains_correct', () => {
    expect(normalizePtBrDecimal('0,10')).toBe('0.10');
    expect(normalizePtBrDecimal('3600')).toBe('3600');
  });

  test('rejects zero, negative, mixed separators and arbitrary text', () => {
    expect(normalizePtBrDecimal('0')).toBeNull();
    expect(normalizePtBrDecimal('-0,1')).toBeNull();
    expect(normalizePtBrDecimal('1,2.3')).toBeNull();
    expect(normalizePtBrDecimal('um')).toBeNull();
  });

  test('presets only fill the declared physical volume', () => {
    expect(VOLUME_PRESETS).toEqual(['450', '900', '3600']);
  });

  test('builds multiple operator components and leaves masses unchanged', () => {
    const payload = buildAdjustmentPayload({
      system: 'POLYESTER_BASECOAT', finish: 'METALLIC', volume: '900', reason: 'decisão manual',
      components: [
        { pigmentCode: 'bp226', quantity: '0,10' },
        { pigmentCode: 'BP201', quantity: '0,05' },
      ],
    });
    expect(payload?.components).toEqual([
      { pigment_code: 'BP226', quantity_g: '0.10' },
      { pigment_code: 'BP201', quantity_g: '0.05' },
    ]);
    expect(payload).not.toHaveProperty('recommended_quantity');
  });

  test('does not create an implicit quantity for an empty component', () => {
    expect(buildAdjustmentPayload({
      system: 'PU', finish: 'SOLID', volume: '450', reason: 'operador',
      components: [{ pigmentCode: 'BP226', quantity: '' }],
    })).toBeNull();
  });

  test('locks editing and confirmation after physical application', () => {
    expect(canEditAdjustment(adjustment('PLANNED'))).toBe(true);
    expect(canEditAdjustment(adjustment('APPLIED_WAITING_FOR_AFTER'))).toBe(false);
    expect(needsPhysicalConfirmation(adjustment('PLANNED'))).toBe(true);
    expect(needsPhysicalConfirmation(adjustment('COMPLETED'))).toBe(false);
  });

  test('keeps the mandatory operator and duplicate-application warnings verbatim', () => {
    expect(APPLIED_WARNING).toBe('NÃO ADICIONE O PIGMENTO NOVAMENTE.');
    expect(OPERATOR_QUANTITY_NOTICE).toContain('não calculou esta dosagem');
  });

  test('after_timeout_preserves_pending_state', () => {
    const pending = adjustment('APPLIED_WAITING_FOR_AFTER');
    expect(preservePendingAfterTimeout(pending)).toBe(pending);
    expect(pending.lifecycle).toBe('APPLIED_WAITING_FOR_AFTER');
  });

  test('completed_result_displays_before_and_after', () => {
    const completed = {
      lifecycle: 'COMPLETED', target_measurement_id: 12,
      before_measurement_id: 13, after_measurement_id: 14,
      observed_response: [], outcomes: [], worst_angle_before: 15, worst_angle_after: 45,
    } as unknown as Adjustment;
    expect(completedResultData(completed)).toMatchObject({
      targetMeasurementId: 12, beforeMeasurementId: 13, afterMeasurementId: 14,
    });
  });

  test('outcome_is_rendered_from_api and mobile_does_not_calculate_observed_response', () => {
    const apiResponse = [{ angle: 15, response_l: 1.25, response_a: -0.5, response_b: 0.2 }];
    const apiOutcomes = [{ angle: 15, delta_e_outcome: 'IMPROVED', delta_e_improvement: 0.7 }];
    const completed = {
      lifecycle: 'COMPLETED', target_measurement_id: 12, before_measurement_id: 13,
      after_measurement_id: 14, observed_response: apiResponse, outcomes: apiOutcomes,
      worst_angle_before: 15, worst_angle_after: 15,
    } as unknown as Adjustment;
    const presented = completedResultData(completed)!;
    expect(presented.observedResponse).toBe(apiResponse);
    expect(presented.outcomes).toBe(apiOutcomes);
  });
});
