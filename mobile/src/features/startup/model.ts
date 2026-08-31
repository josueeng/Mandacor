import { MandacorApiError } from '@/src/api/errors';
import { HealthResponse, InstrumentStatus, RemoteState } from '@/src/types/api';

export const REQUIRED_API_VERSION = 'v1';
export const ERROR_BOUNDARY_COPY = {
  title: 'O MANDACOR encontrou um erro.',
  retry: 'TENTAR NOVAMENTE',
  home: 'VOLTAR AO INÍCIO',
} as const;

export function assertCompatibleServer(health: HealthResponse): HealthResponse {
  if (health.api_version !== REQUIRED_API_VERSION) {
    throw new MandacorApiError(
      'SERVER_VERSION_INCOMPATIBLE',
      `Mobile requires ${REQUIRED_API_VERSION}; server reported ${health.api_version || 'unknown'}.`,
      null,
      { required: REQUIRED_API_VERSION, received: health.api_version },
    );
  }
  return health;
}

export function instrumentRemoteState(
  apiState: RemoteState,
  instrument: InstrumentStatus | null,
): RemoteState {
  if (apiState !== 'ONLINE' || instrument === null) return 'UNKNOWN';
  return instrument.connected ? 'ONLINE' : 'OFFLINE';
}

export function shouldResumeOperation(status: string): boolean {
  return status === 'PREPARED' || status === 'WAITING';
}

export function operationNeedsWaitRequest(status: string): boolean {
  return status === 'PREPARED';
}

export class CriticalActionGuard {
  private readonly active = new Set<string>();

  tryStart(key: string): boolean {
    if (this.active.has(key)) return false;
    this.active.add(key);
    return true;
  }

  finish(key: string): void {
    this.active.delete(key);
  }
}

export function errorRecoveryCode(error: unknown): string {
  return error instanceof Error && error.name ? error.name : 'SCREEN_ERROR';
}

export function operationRecoveryAction(status: string): 'WAIT' | 'POLL' | 'REFRESH' | 'RETRY' | 'CLEAR' {
  if (status === 'PREPARED') return 'WAIT';
  if (status === 'WAITING') return 'POLL';
  if (status === 'COMPLETED') return 'REFRESH';
  if (status === 'TIMED_OUT') return 'RETRY';
  return 'CLEAR';
}

export function homeOperationalPriority(hasPending: boolean): 'PENDING' | 'SESSION' {
  return hasPending ? 'PENDING' : 'SESSION';
}
