import { friendlyError, MandacorApiError, parseApiError } from '@/src/api/errors';

describe('API errors', () => {
  test('parses the P1 error envelope', () => {
    const error = parseApiError(409, {
      error: { code: 'SESSION_NOT_READY', message: 'not ready', details: { state: 'WAITING' } },
    });
    expect(error).toBeInstanceOf(MandacorApiError);
    expect(error.code).toBe('SESSION_NOT_READY');
    expect(error.details).toEqual({ state: 'WAITING' });
  });

  test('preserves request ID for technical support without exposing a stack trace', () => {
    const error = parseApiError(500, {
      error: { code: 'INTERNAL_SERVER_ERROR', message: 'unexpected', details: {}, request_id: 'req-123' },
    });
    expect(error.requestId).toBe('req-123');
    expect(error.message).not.toContain('Traceback');
  });

  test('maps semantic errors to friendly messages', () => {
    expect(friendlyError(new MandacorApiError('MEASUREMENT_TIMEOUT', 'raw', 504))).toBe(
      'Nenhuma nova leitura foi detectada.',
    );
    expect(friendlyError(new MandacorApiError('API_OFFLINE', 'raw', null))).toBe(
      'Servidor MANDACOR offline.',
    );
  });
});
