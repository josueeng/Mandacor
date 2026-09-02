import {
  Adjustment,
  AdjustmentCreatePayload,
  CaptureOperation,
  ColorSession,
  Comparison,
  ConnectResponse,
  CorrectionNeed,
  Diagnosis,
  FinishType,
  FormulaProduct,
  FormulaReading,
  FormulaSearchResult,
  FormulaSearchFilters,
  FormulaSpectralMatchResult,
  FormulaSystem,
  FormulaUpsertPayload,
  MetallicGrain,
  HealthResponse,
  InstrumentStatus,
  PaintSystem,
  PigmentRecommendation,
} from '@/src/types/api';
import { MandacorApiError, parseApiError } from './errors';
import { assertCompatibleServer } from '@/src/features/startup/model';

export function normalizeBaseUrl(value: string): string {
  const trimmed = value.trim().replace(/\/+$/, '');
  if (!/^https?:\/\/[^\s]+$/i.test(trimmed)) {
    throw new MandacorApiError('INVALID_API_URL', 'Use uma URL HTTP válida.', null);
  }
  return trimmed;
}

export class MandacorApiClient {
  readonly baseUrl: string;

  constructor(baseUrl: string, private readonly defaultTimeoutMs = 8000) {
    this.baseUrl = normalizeBaseUrl(baseUrl);
  }

  private async request<T>(
    path: string,
    options: RequestInit = {},
    timeoutMs = this.defaultTimeoutMs,
  ): Promise<T> {
    const controller = new AbortController();
    let timeout!: ReturnType<typeof setTimeout>;
    const timeoutFailure = new Promise<never>((_, reject) => {
      timeout = setTimeout(() => {
        controller.abort();
        reject(new MandacorApiError('REQUEST_TIMEOUT', 'Request timeout.', null));
      }, timeoutMs);
    });
    try {
      const response = await Promise.race([
        fetch(`${this.baseUrl}${path}`, {
          ...options,
          signal: controller.signal,
          headers: {
            Accept: 'application/json',
            ...(options.body ? { 'Content-Type': 'application/json' } : {}),
            ...options.headers,
          },
        }),
        timeoutFailure,
      ]);
      const text = await response.text();
      const payload: unknown = text ? JSON.parse(text) : null;
      if (!response.ok) throw parseApiError(response.status, payload);
      return payload as T;
    } catch (error) {
      if (error instanceof MandacorApiError) throw error;
      if (error instanceof Error && error.name === 'AbortError') {
        throw new MandacorApiError('REQUEST_TIMEOUT', 'Request timeout.', null);
      }
      throw new MandacorApiError('API_OFFLINE', 'Unable to reach MANDACOR API.', null);
    } finally {
      clearTimeout(timeout);
    }
  }

  async health(): Promise<HealthResponse> {
    return assertCompatibleServer(await this.request('/health', {}, 4000));
  }

  instrumentStatus(): Promise<InstrumentStatus> {
    return this.request('/api/v1/instrument/status');
  }

  searchFormulas(
    query: string,
    system?: FormulaSystem,
    limit = 30,
    offset = 0,
    filters: FormulaSearchFilters = {},
  ): Promise<FormulaSearchResult> {
    const parameters = [
      `q=${encodeURIComponent(query.trim())}`,
      `limit=${limit}`,
      `offset=${offset}`,
      ...(system ? [`system=${encodeURIComponent(system)}`] : []),
      ...(filters.manufacturer?.trim() ? [`manufacturer=${encodeURIComponent(filters.manufacturer.trim())}`] : []),
      ...(filters.year?.trim() ? [`year=${encodeURIComponent(filters.year.trim())}`] : []),
      ...(filters.finish?.trim() ? [`finish=${encodeURIComponent(filters.finish.trim())}`] : []),
      ...(filters.universalCode?.trim() ? [`universal_code=${encodeURIComponent(filters.universalCode.trim())}`] : []),
    ];
    return this.request(`/api/v1/formulas?${parameters.join('&')}`);
  }

  getFormula(productCode: string): Promise<FormulaProduct> {
    return this.request(`/api/v1/formulas/${encodeURIComponent(productCode)}`);
  }

  createFormula(payload: FormulaUpsertPayload): Promise<FormulaProduct> {
    return this.request('/api/v1/formulas', {
      method: 'POST', body: JSON.stringify(payload),
    });
  }

  updateFormula(productCode: string, payload: FormulaUpsertPayload): Promise<FormulaProduct> {
    return this.request(`/api/v1/formulas/${encodeURIComponent(productCode)}`, {
      method: 'PUT', body: JSON.stringify(payload),
    });
  }

  deleteFormula(productCode: string): Promise<void> {
    return this.request(`/api/v1/formulas/${encodeURIComponent(productCode)}`, {
      method: 'DELETE',
    });
  }

  formulaReadings(productCode: string): Promise<FormulaReading[]> {
    return this.request(`/api/v1/formulas/${encodeURIComponent(productCode)}/readings`);
  }

  formulaSpectralMatches(
    sessionId: string,
    measurementRole: 'target' | 'sample',
    limit = 30,
  ): Promise<FormulaSpectralMatchResult> {
    return this.request(
      `/api/v1/formulas/spectral-matches?session_id=${encodeURIComponent(sessionId)}&measurement_role=${measurementRole}&limit=${limit}`,
    );
  }

  saveFormulaReading(
    productCode: string,
    sessionId: string,
    formulaId: number,
    metallicGrain: MetallicGrain | null,
    notes = '',
  ): Promise<FormulaReading> {
    return this.request(`/api/v1/formulas/${encodeURIComponent(productCode)}/readings`, {
      method: 'POST',
      body: JSON.stringify({
        session_id: sessionId,
        measurement_role: 'sample',
        formula_id: formulaId,
        metallic_grain: metallicGrain,
        notes,
      }),
    });
  }

  connect(mode: 'auto' | 'manual', host?: string): Promise<ConnectResponse> {
    return this.request('/api/v1/instrument/connect', {
      method: 'POST',
      body: JSON.stringify({ mode, ...(host ? { host } : {}) }),
    }, 15000);
  }

  disconnect(): Promise<InstrumentStatus> {
    return this.request('/api/v1/instrument/disconnect', { method: 'POST' });
  }

  createSession(): Promise<ColorSession> {
    return this.request('/api/v1/sessions', { method: 'POST' });
  }

  getSession(sessionId: string): Promise<ColorSession> {
    return this.request(`/api/v1/sessions/${sessionId}`);
  }

  prepareCapture(sessionId: string, type: 'target' | 'sample'): Promise<CaptureOperation> {
    return this.request(`/api/v1/sessions/${sessionId}/${type}/prepare`, { method: 'POST' });
  }

  replaceWithLatest(sessionId: string, type: 'target' | 'sample'): Promise<ColorSession> {
    return this.request(
      `/api/v1/sessions/${sessionId}/${type}/replace-with-latest`,
      { method: 'POST' },
      65000,
    );
  }

  getOperation(operationId: string): Promise<CaptureOperation> {
    return this.request(`/api/v1/operations/${operationId}`);
  }

  waitOperation(operationId: string): Promise<CaptureOperation> {
    return this.request(
      `/api/v1/operations/${operationId}/wait`,
      { method: 'POST', body: JSON.stringify({ timeout: 60, poll_interval: 0.5 }) },
      65000,
    );
  }

  cancelOperation(operationId: string): Promise<CaptureOperation> {
    return this.request(`/api/v1/operations/${operationId}/cancel`, { method: 'POST' });
  }

  comparison(sessionId: string): Promise<Comparison> {
    return this.request(`/api/v1/sessions/${sessionId}/comparison`);
  }

  diagnosis(sessionId: string): Promise<Diagnosis> {
    return this.request(`/api/v1/sessions/${sessionId}/diagnosis`);
  }

  correction(sessionId: string): Promise<CorrectionNeed> {
    return this.request(`/api/v1/sessions/${sessionId}/correction-needs`);
  }

  pigmentCandidates(
    sessionId: string,
    system: PaintSystem,
    finish: FinishType,
  ): Promise<PigmentRecommendation> {
    return this.request(`/api/v1/sessions/${sessionId}/pigment-candidates`, {
      method: 'POST',
      body: JSON.stringify({ system, finish }),
    });
  }

  createAdjustment(sessionId: string, payload: AdjustmentCreatePayload): Promise<Adjustment> {
    return this.request(`/api/v1/sessions/${sessionId}/adjustments`, {
      method: 'POST', body: JSON.stringify(payload),
    });
  }

  listAdjustments(sessionId: string): Promise<Adjustment[]> {
    return this.request(`/api/v1/sessions/${sessionId}/adjustments`);
  }

  getAdjustment(adjustmentId: string): Promise<Adjustment> {
    return this.request(`/api/v1/adjustments/${adjustmentId}`);
  }

  pendingAdjustment(): Promise<Adjustment | null> {
    return this.request('/api/v1/adjustments/pending');
  }

  confirmAdjustmentApplied(adjustmentId: string): Promise<Adjustment> {
    return this.request(`/api/v1/adjustments/${adjustmentId}/confirm-applied`, { method: 'POST' });
  }

  prepareAdjustmentAfter(adjustmentId: string, retry = false): Promise<CaptureOperation> {
    return this.request(`/api/v1/adjustments/${adjustmentId}/after/${retry ? 'retry' : 'prepare'}`, {
      method: 'POST',
    });
  }

  abandonAdjustment(adjustmentId: string, observation: string): Promise<Adjustment> {
    return this.request(`/api/v1/adjustments/${adjustmentId}/abandon`, {
      method: 'POST', body: JSON.stringify({ observation }),
    });
  }

  submitAdjustmentFeedback(
    adjustmentId: string,
    visualResult: NonNullable<Adjustment['visual_result']>,
    operatorStatus: NonNullable<Adjustment['operator_status']>,
    observations: string,
  ): Promise<Adjustment> {
    return this.request(`/api/v1/adjustments/${adjustmentId}/feedback`, {
      method: 'POST',
      body: JSON.stringify({
        visual_result: visualResult,
        operator_status: operatorStatus,
        observations: observations.trim() || null,
      }),
    });
  }
}
