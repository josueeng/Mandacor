import { MandacorApiError } from '@/src/api/errors';
import { Adjustment } from '@/src/types/api';

interface AdjustmentReader {
  confirmAdjustmentApplied(id: string): Promise<Adjustment>;
  getAdjustment(id: string): Promise<Adjustment>;
  pendingAdjustment(): Promise<Adjustment | null>;
}

export type ConfirmResult =
  | { adjustment: Adjustment; verificationRequired: false }
  | { adjustment: null; verificationRequired: true };

export async function confirmAppliedWithVerification(
  client: AdjustmentReader,
  adjustmentId: string,
): Promise<ConfirmResult> {
  try {
    return { adjustment: await client.confirmAdjustmentApplied(adjustmentId), verificationRequired: false };
  } catch (error) {
    if (!(error instanceof MandacorApiError) || !['API_OFFLINE', 'REQUEST_TIMEOUT'].includes(error.code)) throw error;
    try {
      const adjustment = await client.getAdjustment(adjustmentId);
      if (adjustment.lifecycle === 'APPLIED_WAITING_FOR_AFTER' || adjustment.lifecycle === 'COMPLETED') {
        return { adjustment, verificationRequired: false };
      }
    } catch {
      // An inconclusive status must never trigger an automatic second confirmation.
    }
    return { adjustment: null, verificationRequired: true };
  }
}

export async function recoverPendingAdjustment(
  client: Pick<AdjustmentReader, 'getAdjustment' | 'pendingAdjustment'>,
  savedAdjustmentId: string | null,
): Promise<Adjustment | null> {
  if (savedAdjustmentId) {
    try {
      const saved = await client.getAdjustment(savedAdjustmentId);
      if (saved.lifecycle === 'APPLIED_WAITING_FOR_AFTER') return saved;
    } catch {
      // Fall through to the authoritative global pending endpoint.
    }
  }
  return client.pendingAdjustment();
}
