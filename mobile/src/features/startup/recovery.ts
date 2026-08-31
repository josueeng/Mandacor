import { MandacorApiError } from '@/src/api/errors';
import { CaptureOperation, ColorSession } from '@/src/types/api';

interface RecoveryClient {
  getSession(id: string): Promise<ColorSession>;
  getOperation(id: string): Promise<CaptureOperation>;
}

export type RecoveryResult<T> = { value: T | null; stale: boolean };

export async function recoverSession(
  client: Pick<RecoveryClient, 'getSession'>,
  sessionId: string | null,
): Promise<RecoveryResult<ColorSession>> {
  if (!sessionId) return { value: null, stale: false };
  try {
    return { value: await client.getSession(sessionId), stale: false };
  } catch (error) {
    if (error instanceof MandacorApiError && error.code === 'SESSION_NOT_FOUND') {
      return { value: null, stale: true };
    }
    throw error;
  }
}

export async function recoverOperation(
  client: Pick<RecoveryClient, 'getOperation'>,
  operationId: string | null,
): Promise<RecoveryResult<CaptureOperation>> {
  if (!operationId) return { value: null, stale: false };
  try {
    return { value: await client.getOperation(operationId), stale: false };
  } catch (error) {
    if (error instanceof MandacorApiError && error.code === 'OPERATION_NOT_FOUND') {
      return { value: null, stale: true };
    }
    throw error;
  }
}
