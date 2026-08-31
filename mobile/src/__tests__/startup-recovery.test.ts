import { MandacorApiError } from '@/src/api/errors';
import { recoverOperation, recoverSession } from '@/src/features/startup/recovery';
import { CaptureOperation, ColorSession } from '@/src/types/api';

describe('startup backend reconciliation', () => {
  test('startup_restores_session', async () => {
    const session = { session_id: 'session-1', state: 'TARGET_CAPTURED' } as ColorSession;
    const client = { getSession: jest.fn().mockResolvedValue(session) };
    await expect(recoverSession(client, 'session-1')).resolves.toEqual({ value: session, stale: false });
    expect(client.getSession).toHaveBeenCalledTimes(1);
  });

  test('missing session is explicitly stale while offline is not silently cleared', async () => {
    const missing = { getSession: jest.fn().mockRejectedValue(new MandacorApiError('SESSION_NOT_FOUND', 'missing', 404)) };
    await expect(recoverSession(missing, 'session-1')).resolves.toEqual({ value: null, stale: true });
    const offline = { getSession: jest.fn().mockRejectedValue(new MandacorApiError('API_OFFLINE', 'offline', null)) };
    await expect(recoverSession(offline, 'session-1')).rejects.toMatchObject({ code: 'API_OFFLINE' });
  });

  test('startup_restores_active_operation_without_preparing_another', async () => {
    const operation = { operation_id: 'op-1', status: 'WAITING' } as CaptureOperation;
    const client = { getOperation: jest.fn().mockResolvedValue(operation) };
    await expect(recoverOperation(client, 'op-1')).resolves.toEqual({ value: operation, stale: false });
    expect(client.getOperation).toHaveBeenCalledTimes(1);
  });
});
