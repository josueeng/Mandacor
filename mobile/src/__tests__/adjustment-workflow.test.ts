import { MandacorApiError } from '@/src/api/errors';
import { confirmAppliedWithVerification, recoverPendingAdjustment } from '@/src/features/adjustments/workflow';
import { Adjustment } from '@/src/types/api';

const item = (lifecycle: Adjustment['lifecycle'], id = 'adjustment-1') => ({
  adjustment_id: id, lifecycle,
} as Adjustment);

describe('safety-critical adjustment orchestration', () => {
  test('accepts a successful physical confirmation once', async () => {
    const client = {
      confirmAdjustmentApplied: jest.fn().mockResolvedValue(item('APPLIED_WAITING_FOR_AFTER')),
      getAdjustment: jest.fn(), pendingAdjustment: jest.fn(),
    };
    const result = await confirmAppliedWithVerification(client, 'adjustment-1');
    expect(result.adjustment?.lifecycle).toBe('APPLIED_WAITING_FOR_AFTER');
    expect(client.confirmAdjustmentApplied).toHaveBeenCalledTimes(1);
    expect(client.getAdjustment).not.toHaveBeenCalled();
  });

  test('checks status after an ambiguous response and never confirms twice', async () => {
    const client = {
      confirmAdjustmentApplied: jest.fn().mockRejectedValue(new MandacorApiError('REQUEST_TIMEOUT', 'timeout', null)),
      getAdjustment: jest.fn().mockResolvedValue(item('APPLIED_WAITING_FOR_AFTER')),
      pendingAdjustment: jest.fn(),
    };
    const result = await confirmAppliedWithVerification(client, 'adjustment-1');
    expect(result.verificationRequired).toBe(false);
    expect(client.confirmAdjustmentApplied).toHaveBeenCalledTimes(1);
    expect(client.getAdjustment).toHaveBeenCalledWith('adjustment-1');
  });

  test('requires explicit verification when both confirmation and status are inconclusive', async () => {
    const client = {
      confirmAdjustmentApplied: jest.fn().mockRejectedValue(new MandacorApiError('API_OFFLINE', 'offline', null)),
      getAdjustment: jest.fn().mockRejectedValue(new MandacorApiError('API_OFFLINE', 'offline', null)),
      pendingAdjustment: jest.fn(),
    };
    await expect(confirmAppliedWithVerification(client, 'adjustment-1')).resolves.toEqual({
      adjustment: null, verificationRequired: true,
    });
    expect(client.confirmAdjustmentApplied).toHaveBeenCalledTimes(1);
  });

  test('recovers the exact saved pending ID after restart', async () => {
    const pending = item('APPLIED_WAITING_FOR_AFTER', 'same-id');
    const client = { getAdjustment: jest.fn().mockResolvedValue(pending), pendingAdjustment: jest.fn() };
    await expect(recoverPendingAdjustment(client, 'same-id')).resolves.toBe(pending);
    expect(client.pendingAdjustment).not.toHaveBeenCalled();
  });

  test('falls back to the authoritative pending endpoint', async () => {
    const pending = item('APPLIED_WAITING_FOR_AFTER');
    const client = { getAdjustment: jest.fn().mockRejectedValue(new Error('restart')), pendingAdjustment: jest.fn().mockResolvedValue(pending) };
    await expect(recoverPendingAdjustment(client, 'old-id')).resolves.toBe(pending);
  });
});
