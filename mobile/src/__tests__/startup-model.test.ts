import {
  assertCompatibleServer,
  CriticalActionGuard,
  ERROR_BOUNDARY_COPY,
  homeOperationalPriority,
  instrumentRemoteState,
  operationNeedsWaitRequest,
  operationRecoveryAction,
  shouldResumeOperation,
} from '@/src/features/startup/model';
import { HealthResponse } from '@/src/types/api';

const health: HealthResponse = {
  status: 'ok', service: 'mandacor', version: '0.4.0', api_version: 'v1',
  recovery: 'OK', recovery_error: null,
};

describe('P4 startup and operational recovery', () => {
  test('startup_api_offline_does_not_crash', () => {
    expect(() => instrumentRemoteState('OFFLINE', null)).not.toThrow();
    expect(instrumentRemoteState('OFFLINE', null)).toBe('UNKNOWN');
  });

  test('startup_restores_session through the authoritative backend state', () => {
    expect(operationRecoveryAction('COMPLETED')).toBe('REFRESH');
  });

  test('startup_restores_active_operation', () => {
    expect(shouldResumeOperation('PREPARED')).toBe(true);
    expect(shouldResumeOperation('WAITING')).toBe(true);
  });

  test('startup_restores_pending_adjustment with Home priority', () => {
    expect(homeOperationalPriority(true)).toBe('PENDING');
  });

  test('unknown_api_state_is_not_shown_as_instrument_disconnected', () => {
    expect(instrumentRemoteState('UNKNOWN', { connected: false, instrument: null })).toBe('UNKNOWN');
    expect(instrumentRemoteState('ONLINE', { connected: false, instrument: null })).toBe('OFFLINE');
  });

  test('background_capture_resumes_correctly', () => {
    expect(operationRecoveryAction('WAITING')).toBe('POLL');
  });

  test('completed_operation_stops_polling', () => {
    expect(shouldResumeOperation('COMPLETED')).toBe(false);
    expect(operationRecoveryAction('COMPLETED')).not.toBe('POLL');
  });

  test('app_restart_does_not_duplicate_operation', () => {
    expect(operationNeedsWaitRequest('WAITING')).toBe(false);
    expect(operationNeedsWaitRequest('PREPARED')).toBe(true);
  });

  test('double-submit guard permits only one target/sample/confirm/after action', () => {
    const guard = new CriticalActionGuard();
    for (const key of ['target', 'sample', 'confirm', 'after']) {
      expect(guard.tryStart(key)).toBe(true);
      expect(guard.tryStart(key)).toBe(false);
      guard.finish(key);
      expect(guard.tryStart(key)).toBe(true);
      guard.finish(key);
    }
  });

  test('pending_has_home_priority', () => {
    expect(homeOperationalPriority(true)).toBe('PENDING');
    expect(homeOperationalPriority(false)).toBe('SESSION');
  });

  test('compatible API v1 is accepted', () => {
    expect(assertCompatibleServer(health)).toBe(health);
  });

  test('error_boundary_shows_recovery_ui', () => {
    expect(ERROR_BOUNDARY_COPY).toEqual({
      title: 'O MANDACOR encontrou um erro.', retry: 'TENTAR NOVAMENTE', home: 'VOLTAR AO INÍCIO',
    });
  });
});
