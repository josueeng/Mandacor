import { MandacorApiClient, normalizeBaseUrl } from '@/src/api/client';
import { MandacorApiError } from '@/src/api/errors';

const mockFetch = jest.fn<Promise<Response>, Parameters<typeof fetch>>();
globalThis.fetch = mockFetch as typeof fetch;

describe('MandacorApiClient', () => {
  beforeEach(() => mockFetch.mockReset());

  test('normalizes a configurable server URL', () => {
    expect(normalizeBaseUrl(' http://192.168.1.11:8000/ ')).toBe('http://192.168.1.11:8000');
    expect(() => normalizeBaseUrl('192.168.1.11:8000')).toThrow(MandacorApiError);
  });

  test('parses health from the real P1 route contract', async () => {
    const health = { status: 'ok', service: 'mandacor', version: '0.4.0', api_version: 'v1', recovery: 'OK', recovery_error: null };
    mockFetch.mockResolvedValue(new Response(JSON.stringify(health), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));
    const client = new MandacorApiClient('http://192.168.1.11:8000');
    await expect(client.health()).resolves.toEqual(health);
    expect(mockFetch).toHaveBeenCalledWith(
      'http://192.168.1.11:8000/health',
      expect.objectContaining({ signal: expect.anything() }),
    );
  });

  test('server_version_mismatch_is_detected', async () => {
    mockFetch.mockResolvedValue(new Response(JSON.stringify({
      status: 'ok', service: 'mandacor', version: '9.0.0', api_version: 'v9',
      recovery: 'OK', recovery_error: null,
    }), { status: 200 }));
    await expect(new MandacorApiClient('http://localhost:8000').health()).rejects.toMatchObject({
      code: 'SERVER_VERSION_INCOMPATIBLE',
    });
  });

  test('logical timeout releases a request even when fetch ignores abort', async () => {
    mockFetch.mockImplementation(() => new Promise<Response>(() => undefined));
    const client = new MandacorApiClient('http://localhost:8000', 10);
    await expect(client.instrumentStatus()).rejects.toMatchObject({
      code: 'REQUEST_TIMEOUT',
    });
  });

  test('preserves backend semantic error code', async () => {
    mockFetch.mockResolvedValue(new Response(JSON.stringify({
      error: { code: 'INSTRUMENT_UNAVAILABLE', message: 'offline', details: {} },
    }), { status: 503 }));
    const client = new MandacorApiClient('http://localhost:8000');
    await expect(client.instrumentStatus()).rejects.toMatchObject({
      code: 'INSTRUMENT_UNAVAILABLE',
      status: 503,
    });
  });

  test('retries AFTER with the same adjustment ID and no quantity body', async () => {
    mockFetch.mockResolvedValue(new Response(JSON.stringify({ operation_id: 'op-2' }), { status: 201 }));
    const client = new MandacorApiClient('http://localhost:8000');
    await client.prepareAdjustmentAfter('adjustment-1', true);
    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/adjustments/adjustment-1/after/retry',
      expect.objectContaining({ method: 'POST' }),
    );
    expect(mockFetch.mock.calls[0][1]).not.toHaveProperty('body');
  });

  test('sends only operator-entered adjustment values', async () => {
    mockFetch.mockResolvedValue(new Response(JSON.stringify({ adjustment_id: 'a-1' }), { status: 201 }));
    const client = new MandacorApiClient('http://localhost:8000');
    await client.createAdjustment('session-1', {
      system: 'POLYESTER_BASECOAT', finish: 'METALLIC', volume_ml: '450',
      components: [{ pigment_code: 'BP226', quantity_g: '0.10' }], operator_reason: 'manual',
    });
    const request = mockFetch.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(request.body as string)).toEqual({
      system: 'POLYESTER_BASECOAT', finish: 'METALLIC', volume_ml: '450',
      components: [{ pigment_code: 'BP226', quantity_g: '0.10' }], operator_reason: 'manual',
    });
  });
});
