import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  AppState as NativeAppState,
  AppStateStatus,
  Platform,
} from 'react-native';
import {
  createContext,
  PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import { MandacorApiClient, normalizeBaseUrl } from '@/src/api/client';
import { friendlyError, MandacorApiError } from '@/src/api/errors';
import { recoverPendingAdjustment } from '@/src/features/adjustments/workflow';
import {
  Adjustment,
  CaptureOperation,
  ColorSession,
  DiscoveredInstrument,
  InstrumentStatus,
  RemoteState,
} from '@/src/types/api';
import { CriticalActionGuard, operationNeedsWaitRequest, shouldResumeOperation } from '@/src/features/startup/model';
import { recoverOperation, recoverSession } from '@/src/features/startup/recovery';

const STORAGE = {
  baseUrl: '@mandacor/base-url',
  sessionId: '@mandacor/session-id',
  operationId: '@mandacor/operation-id',
  pendingAdjustmentId: '@mandacor/pending-adjustment-id',
} as const;

const DEFAULT_URL = process.env.EXPO_PUBLIC_MANDACOR_API_URL ?? 'http://127.0.0.1:8000';
const FORCE_ENV_URL = process.env.EXPO_PUBLIC_MANDACOR_FORCE_API_URL === '1';
const TERMINAL = new Set(['COMPLETED', 'TIMED_OUT', 'CANCELLED', 'FAILED']);

export type StartupPhase = 'CONFIG' | 'API' | 'INSTRUMENT' | 'SESSION' | 'OPERATION' | 'PENDING' | 'READY';

interface MandacorState {
  hydrated: boolean;
  baseUrl: string;
  apiOnline: boolean;
  apiState: RemoteState;
  instrumentState: RemoteState;
  instrument: InstrumentStatus;
  candidates: DiscoveredInstrument[];
  currentSession: ColorSession | null;
  activeOperation: CaptureOperation | null;
  pendingAdjustment: Adjustment | null;
  busy: boolean;
  errorMessage: string | null;
  errorTechnicalCode: string | null;
  startupPhase: StartupPhase;
  startupDetail: string;
  lastCheckedAt: string | null;
  latencyMs: number | null;
  serverVersion: string | null;
  setApiUrl: (value: string) => Promise<void>;
  testAndSaveApiUrl: (value: string) => Promise<boolean>;
  testApi: () => Promise<boolean>;
  refreshInstrument: () => Promise<void>;
  connectInstrument: (mode: 'auto' | 'manual', host?: string) => Promise<void>;
  disconnectInstrument: () => Promise<void>;
  createComparison: () => Promise<void>;
  refreshSession: () => Promise<void>;
  prepareCapture: (type: 'target' | 'sample') => Promise<void>;
  replaceWithLatest: (type: 'target' | 'sample') => Promise<void>;
  cancelCapture: () => Promise<void>;
  refreshPendingAdjustment: () => Promise<void>;
  startAfterCapture: (adjustmentId: string, retry?: boolean) => Promise<void>;
  clearError: () => void;
  enterAnyway: () => void;
}

const AppContext = createContext<MandacorState | null>(null);

export function AppProvider({ children }: PropsWithChildren) {
  const [hydrated, setHydrated] = useState(false);
  const [baseUrl, setBaseUrl] = useState(DEFAULT_URL);
  const [apiOnline, setApiOnline] = useState(false);
  const [apiState, setApiState] = useState<RemoteState>('UNKNOWN');
  const [instrumentState, setInstrumentState] = useState<RemoteState>('UNKNOWN');
  const [instrument, setInstrument] = useState<InstrumentStatus>({ connected: false, instrument: null });
  const [candidates, setCandidates] = useState<DiscoveredInstrument[]>([]);
  const [currentSession, setCurrentSession] = useState<ColorSession | null>(null);
  const [activeOperation, setActiveOperation] = useState<CaptureOperation | null>(null);
  const [pendingAdjustment, setPendingAdjustment] = useState<Adjustment | null>(null);
  const [busy, setBusy] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [errorTechnicalCode, setErrorTechnicalCode] = useState<string | null>(null);
  const [startupPhase, setStartupPhase] = useState<StartupPhase>('CONFIG');
  const [startupDetail, setStartupDetail] = useState('Carregando configuração local');
  const [lastCheckedAt, setLastCheckedAt] = useState<string | null>(null);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [serverVersion, setServerVersion] = useState<string | null>(null);
  const monitorToken = useRef(0);
  const pollInterval = useRef<ReturnType<typeof setInterval> | null>(null);
  const waitingRequest = useRef<string | null>(null);
  const activeOperationRef = useRef<CaptureOperation | null>(null);
  const criticalActions = useRef(new CriticalActionGuard());
  const client = useMemo(() => new MandacorApiClient(baseUrl), [baseUrl]);

  useEffect(() => {
    activeOperationRef.current = activeOperation;
  }, [activeOperation]);

  const handleError = useCallback((error: unknown) => {
    if (error instanceof MandacorApiError) {
      setErrorTechnicalCode(error.requestId ?? error.code);
      if (error.code === 'API_OFFLINE') {
        setApiOnline(false);
        setApiState('OFFLINE');
        setInstrumentState('UNKNOWN');
        setInstrument({ connected: false, instrument: null });
      }
    }
    setErrorMessage(friendlyError(error));
  }, []);

  const bootstrap = useCallback(async (
    url: string,
    sessionId: string | null,
    operationId: string | null,
    pendingAdjustmentId: string | null,
  ) => {
    const restoredClient = new MandacorApiClient(url);
    try {
      setStartupPhase('API');
      setStartupDetail('Verificando servidor MANDACOR');
      const started = Date.now();
      const health = await restoredClient.health();
      setLatencyMs(Date.now() - started);
      setLastCheckedAt(new Date().toISOString());
      setServerVersion(health.version);
      setApiOnline(true);
      setApiState('ONLINE');
      setStartupPhase('INSTRUMENT');
      setStartupDetail('Consultando espectrofotômetro');
      const restoredInstrument = await restoredClient.instrumentStatus();
      setInstrument(restoredInstrument);
      setInstrumentState(restoredInstrument.connected ? 'ONLINE' : 'OFFLINE');
      setStartupPhase('SESSION');
      setStartupDetail('Recuperando sessão');
      const restoredSession = await recoverSession(restoredClient, sessionId);
      setCurrentSession(restoredSession.value);
      if (restoredSession.stale) {
        await AsyncStorage.removeItem(STORAGE.sessionId);
        setErrorMessage('A sessão salva não existe mais no servidor. A referência local foi removida.');
      }
      setStartupPhase('OPERATION');
      setStartupDetail('Reconciliando captura');
      const restoredOperation = await recoverOperation(restoredClient, operationId);
      setActiveOperation(restoredOperation.value);
      if (restoredOperation.stale || (restoredOperation.value && TERMINAL.has(restoredOperation.value.status))) {
        await AsyncStorage.removeItem(STORAGE.operationId);
      }
      setStartupPhase('PENDING');
      setStartupDetail('Verificando ajuste físico pendente');
      const recoveredPending = await recoverPendingAdjustment(restoredClient, pendingAdjustmentId);
      setPendingAdjustment(recoveredPending);
      if (recoveredPending) {
        setCurrentSession(await restoredClient.getSession(recoveredPending.session_id));
        await AsyncStorage.multiSet([
          [STORAGE.pendingAdjustmentId, recoveredPending.adjustment_id],
          [STORAGE.sessionId, recoveredPending.session_id],
        ]);
      } else {
        await AsyncStorage.removeItem(STORAGE.pendingAdjustmentId);
      }
    } catch (error) {
      setApiOnline(false);
      setApiState('OFFLINE');
      setInstrumentState('UNKNOWN');
      setInstrument({ connected: false, instrument: null });
      handleError(error);
    } finally {
      setStartupPhase('READY');
      setStartupDetail('Pronto');
    }
  }, [handleError]);

  useEffect(() => {
    void (async () => {
      const entries = await AsyncStorage.multiGet(Object.values(STORAGE));
      const values = Object.fromEntries(entries);
      let savedUrl = FORCE_ENV_URL ? DEFAULT_URL : values[STORAGE.baseUrl] ?? DEFAULT_URL;
      try {
        savedUrl = normalizeBaseUrl(savedUrl);
        if (FORCE_ENV_URL) await AsyncStorage.setItem(STORAGE.baseUrl, savedUrl);
        if (Platform.OS === 'web') {
          const parsed = new URL(savedUrl);
          if (parsed.hostname === '10.0.2.2') {
            parsed.hostname = 'localhost';
            savedUrl = normalizeBaseUrl(parsed.toString());
            await AsyncStorage.setItem(STORAGE.baseUrl, savedUrl);
          }
        }
      } catch {
        savedUrl = DEFAULT_URL;
      }
      setBaseUrl(savedUrl);
      await bootstrap(
        savedUrl,
        values[STORAGE.sessionId] ?? null,
        values[STORAGE.operationId] ?? null,
        values[STORAGE.pendingAdjustmentId] ?? null,
      );
      setHydrated(true);
    })();
  }, [bootstrap]);

  const setApiUrl = useCallback(async (value: string) => {
    const normalized = normalizeBaseUrl(value);
    await AsyncStorage.setItem(STORAGE.baseUrl, normalized);
    setBaseUrl(normalized);
    setApiOnline(false);
    setApiState('UNKNOWN');
    setInstrumentState('UNKNOWN');
    setErrorMessage(null);
    setErrorTechnicalCode(null);
  }, []);

  const testAndSaveApiUrl = useCallback(async (value: string) => {
    const key = 'test-and-save-server';
    if (!criticalActions.current.tryStart(key)) return false;
    setBusy(true);
    setErrorMessage(null);
    try {
      const normalized = normalizeBaseUrl(value);
      const candidate = new MandacorApiClient(normalized);
      const started = Date.now();
      const health = await candidate.health();
      const latestInstrument = await candidate.instrumentStatus();
      await AsyncStorage.setItem(STORAGE.baseUrl, normalized);
      setBaseUrl(normalized);
      setLatencyMs(Date.now() - started);
      setLastCheckedAt(new Date().toISOString());
      setServerVersion(health.version);
      setApiOnline(true);
      setApiState('ONLINE');
      setInstrument(latestInstrument);
      setInstrumentState(latestInstrument.connected ? 'ONLINE' : 'OFFLINE');
      return true;
    } catch (error) {
      handleError(error);
      return false;
    } finally {
      criticalActions.current.finish(key);
      setBusy(false);
    }
  }, [handleError]);

  const testApi = useCallback(async () => {
    setBusy(true);
    setErrorMessage(null);
    try {
      const started = Date.now();
      const health = await client.health();
      setLatencyMs(Date.now() - started);
      setLastCheckedAt(new Date().toISOString());
      setServerVersion(health.version);
      setApiOnline(true);
      setApiState('ONLINE');
      const latestInstrument = await client.instrumentStatus();
      setInstrument(latestInstrument);
      setInstrumentState(latestInstrument.connected ? 'ONLINE' : 'OFFLINE');
      return true;
    } catch (error) {
      setApiOnline(false);
      setApiState('OFFLINE');
      setInstrumentState('UNKNOWN');
      setInstrument({ connected: false, instrument: null });
      handleError(error);
      return false;
    } finally {
      setBusy(false);
    }
  }, [client, handleError]);

  const refreshInstrument = useCallback(async () => {
    try {
      const latest = await client.instrumentStatus();
      setInstrument(latest);
      setApiOnline(true);
      setApiState('ONLINE');
      setInstrumentState(latest.connected ? 'ONLINE' : 'OFFLINE');
    } catch (error) {
      handleError(error);
    }
  }, [client, handleError]);

  const connectInstrument = useCallback(async (mode: 'auto' | 'manual', host?: string) => {
    const key = 'connect-instrument';
    if (!criticalActions.current.tryStart(key)) return;
    setBusy(true);
    setErrorMessage(null);
    try {
      const response = await client.connect(mode, host);
      setCandidates(response.instruments);
      if (response.state === 'MULTIPLE_INSTRUMENTS') {
        setErrorMessage('Mais de um espectrofotômetro foi encontrado. Escolha um equipamento.');
      }
      setInstrument({ connected: response.connected, instrument: response.instrument });
      setApiOnline(true);
      setApiState('ONLINE');
      setInstrumentState(response.connected ? 'ONLINE' : 'OFFLINE');
    } catch (error) {
      handleError(error);
    } finally {
      criticalActions.current.finish(key);
      setBusy(false);
    }
  }, [client, handleError]);

  const disconnectInstrument = useCallback(async () => {
    setBusy(true);
    setErrorMessage(null);
    try {
      await client.disconnect();
      setInstrument({ connected: false, instrument: null });
      setInstrumentState('OFFLINE');
      setCandidates([]);
    } catch (error) {
      handleError(error);
    } finally {
      setBusy(false);
    }
  }, [client, handleError]);

  const createComparison = useCallback(async () => {
    const key = 'create-session';
    if (!criticalActions.current.tryStart(key)) return;
    setBusy(true);
    setErrorMessage(null);
    try {
      const session = await client.createSession();
      setCurrentSession(session);
      setActiveOperation(null);
      await AsyncStorage.multiSet([
        [STORAGE.sessionId, session.session_id],
        [STORAGE.operationId, ''],
      ]);
    } catch (error) {
      handleError(error);
    } finally {
      criticalActions.current.finish(key);
      setBusy(false);
    }
  }, [client, handleError]);

  const refreshSession = useCallback(async () => {
    if (!currentSession) return;
    try {
      setCurrentSession(await client.getSession(currentSession.session_id));
    } catch (error) {
      handleError(error);
    }
  }, [client, currentSession, handleError]);

  const monitorOperation = useCallback(async (operation: CaptureOperation) => {
    if (waitingRequest.current === operation.operation_id) return;
    waitingRequest.current = operation.operation_id;
    const token = ++monitorToken.current;
    if (pollInterval.current) clearInterval(pollInterval.current);
    const poll = setInterval(() => {
      void client.getOperation(operation.operation_id).then((latest) => {
        if (monitorToken.current === token) setActiveOperation(latest);
      }).catch(handleError);
    }, 750);
    pollInterval.current = poll;
    try {
      const completedOperation = await client.waitOperation(operation.operation_id);
      if (monitorToken.current === token) {
        setActiveOperation(completedOperation);
        setCurrentSession(await client.getSession(operation.session_id));
        if (TERMINAL.has(completedOperation.status)) {
          await AsyncStorage.removeItem(STORAGE.operationId);
        }
      }
    } catch (error) {
      handleError(error);
    } finally {
      clearInterval(poll);
      if (pollInterval.current === poll) pollInterval.current = null;
      waitingRequest.current = null;
      if (monitorToken.current === token) {
        try {
          const finalOperation = await client.getOperation(operation.operation_id);
          setActiveOperation(finalOperation);
          if (currentSession) setCurrentSession(await client.getSession(currentSession.session_id));
          if (TERMINAL.has(finalOperation.status)) await AsyncStorage.removeItem(STORAGE.operationId);
        } catch (error) {
          handleError(error);
        }
      }
    }
  }, [client, currentSession, handleError]);

  const prepareCapture = useCallback(async (type: 'target' | 'sample') => {
    if (!currentSession) return;
    const key = `prepare-${currentSession.session_id}-${type}`;
    if (!criticalActions.current.tryStart(key)) return;
    setBusy(true);
    setErrorMessage(null);
    try {
      const operation = await client.prepareCapture(currentSession.session_id, type);
      setActiveOperation(operation);
      await AsyncStorage.setItem(STORAGE.operationId, operation.operation_id);
      void monitorOperation(operation);
    } catch (error) {
      handleError(error);
    } finally {
      criticalActions.current.finish(key);
      setBusy(false);
    }
  }, [client, currentSession, handleError, monitorOperation]);

  const replaceWithLatest = useCallback(async (type: 'target' | 'sample') => {
    if (!currentSession) return;
    const key = `replace-latest-${currentSession.session_id}-${type}`;
    if (!criticalActions.current.tryStart(key)) return;
    setBusy(true);
    setErrorMessage(null);
    try {
      const updated = await client.replaceWithLatest(currentSession.session_id, type);
      setCurrentSession(updated);
      setActiveOperation(null);
      await AsyncStorage.removeItem(STORAGE.operationId);
    } catch (error) {
      handleError(error);
    } finally {
      criticalActions.current.finish(key);
      setBusy(false);
    }
  }, [client, currentSession, handleError]);

  const cancelCapture = useCallback(async () => {
    if (!activeOperation || TERMINAL.has(activeOperation.status)) return;
    setBusy(true);
    try {
      monitorToken.current += 1;
      setActiveOperation(await client.cancelOperation(activeOperation.operation_id));
      await AsyncStorage.removeItem(STORAGE.operationId);
    } catch (error) {
      handleError(error);
    } finally {
      setBusy(false);
    }
  }, [activeOperation, client, handleError]);

  const refreshPendingAdjustment = useCallback(async () => {
    try {
      const pending = await client.pendingAdjustment();
      setPendingAdjustment(pending);
      if (pending) {
        await AsyncStorage.setItem(STORAGE.pendingAdjustmentId, pending.adjustment_id);
      } else {
        await AsyncStorage.removeItem(STORAGE.pendingAdjustmentId);
      }
    } catch (error) {
      handleError(error);
    }
  }, [client, handleError]);

  const startAfterCapture = useCallback(async (adjustmentId: string, retry = false) => {
    const key = `prepare-after-${adjustmentId}`;
    if (!criticalActions.current.tryStart(key)) return;
    setBusy(true);
    setErrorMessage(null);
    try {
      const operation = await client.prepareAdjustmentAfter(adjustmentId, retry);
      setActiveOperation(operation);
      await AsyncStorage.multiSet([
        [STORAGE.operationId, operation.operation_id],
        [STORAGE.pendingAdjustmentId, adjustmentId],
      ]);
      void monitorOperation(operation);
    } catch (error) {
      handleError(error);
    } finally {
      criticalActions.current.finish(key);
      setBusy(false);
    }
  }, [client, handleError, monitorOperation]);

  const reconcileOperation = useCallback(async (operation: CaptureOperation) => {
    try {
      const latest = await client.getOperation(operation.operation_id);
      setActiveOperation(latest);
      if (TERMINAL.has(latest.status)) {
        if (pollInterval.current) clearInterval(pollInterval.current);
        pollInterval.current = null;
        await AsyncStorage.removeItem(STORAGE.operationId);
        try {
          setCurrentSession(await client.getSession(latest.session_id));
        } catch {
          // Pending recovery may own a session not present in an older backend.
        }
        await refreshPendingAdjustment();
      }
    } catch (error) {
      handleError(error);
    }
  }, [client, handleError, refreshPendingAdjustment]);

  useEffect(() => {
    if (!hydrated || !activeOperation || !shouldResumeOperation(activeOperation.status)) return;
    if (operationNeedsWaitRequest(activeOperation.status)) {
      void monitorOperation(activeOperation);
      return;
    }
    if (waitingRequest.current === activeOperation.operation_id || pollInterval.current) return;
    const timer = setInterval(() => void reconcileOperation(activeOperation), 750);
    pollInterval.current = timer;
    return () => {
      clearInterval(timer);
      if (pollInterval.current === timer) pollInterval.current = null;
    };
  }, [activeOperation, hydrated, monitorOperation, reconcileOperation]);

  useEffect(() => {
    const onAppStateChange = (nextState: AppStateStatus) => {
      if (nextState !== 'active') {
        if (pollInterval.current) clearInterval(pollInterval.current);
        pollInterval.current = null;
        return;
      }
      const operation = activeOperationRef.current;
      if (operation) void reconcileOperation(operation);
      else void refreshPendingAdjustment();
    };
    const subscription = NativeAppState.addEventListener('change', onAppStateChange);
    return () => {
      subscription.remove();
      if (pollInterval.current) clearInterval(pollInterval.current);
      pollInterval.current = null;
      monitorToken.current += 1;
    };
  }, [reconcileOperation, refreshPendingAdjustment]);

  const value = useMemo<MandacorState>(() => ({
    hydrated,
    baseUrl,
    apiOnline,
    apiState,
    instrumentState,
    instrument,
    candidates,
    currentSession,
    activeOperation,
    pendingAdjustment,
    busy,
    errorMessage,
    errorTechnicalCode,
    startupPhase,
    startupDetail,
    lastCheckedAt,
    latencyMs,
    serverVersion,
    setApiUrl,
    testAndSaveApiUrl,
    testApi,
    refreshInstrument,
    connectInstrument,
    disconnectInstrument,
    createComparison,
    refreshSession,
    prepareCapture,
    replaceWithLatest,
    cancelCapture,
    refreshPendingAdjustment,
    startAfterCapture,
    clearError: () => { setErrorMessage(null); setErrorTechnicalCode(null); },
    enterAnyway: () => { setHydrated(true); setStartupPhase('READY'); },
  }), [
    hydrated, baseUrl, apiOnline, apiState, instrumentState, instrument, candidates, currentSession, activeOperation, pendingAdjustment,
    busy, errorMessage, errorTechnicalCode, startupPhase, startupDetail, lastCheckedAt, latencyMs, serverVersion,
    setApiUrl, testAndSaveApiUrl, testApi, refreshInstrument, connectInstrument,
    disconnectInstrument, createComparison, refreshSession, prepareCapture, replaceWithLatest, cancelCapture,
    refreshPendingAdjustment, startAfterCapture,
  ]);

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useMandacor(): MandacorState {
  const context = useContext(AppContext);
  if (!context) throw new Error('useMandacor must be used within AppProvider');
  return context;
}
