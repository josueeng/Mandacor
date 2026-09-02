import { useEffect, useState } from 'react';
import { StyleSheet, Text } from 'react-native';
import Constants from 'expo-constants';
import { router } from 'expo-router';

import { ActionButton, Card, ErrorNotice, Field, Screen, ScreenHeader, SectionHeader, StatusBadge, uiStyles } from '@/src/components/ui';
import { presentState } from '@/src/presentation/format';
import { useMandacor } from '@/src/state/AppContext';
import { colors } from '@/src/theme/tokens';

function splitUrl(baseUrl: string): { host: string; port: string } {
  try {
    const parsed = new URL(baseUrl);
    return { host: parsed.hostname, port: parsed.port || (parsed.protocol === 'https:' ? '443' : '80') };
  } catch {
    return { host: '', port: '8000' };
  }
}

export default function SettingsScreen() {
  const state = useMandacor();
  const initial = splitUrl(state.baseUrl);
  const [host, setHost] = useState(initial.host);
  const [port, setPort] = useState(initial.port);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const parsed = splitUrl(state.baseUrl);
    setHost(parsed.host);
    setPort(parsed.port);
  }, [state.baseUrl]);

  const save = async () => {
    setSaved(await state.testAndSaveApiUrl(`http://${host.trim()}:${port.trim()}`));
  };

  return (
    <Screen>
      <ScreenHeader
        eyebrow="CONFIGURAÇÃO"
        title="Central de conexão"
        subtitle="Servidor local, espectrofotômetro e informações técnicas do aplicativo."
      />
      <ErrorNotice message={state.errorMessage} />
      <Card tone="info">
        <SectionHeader>REGISTROS</SectionHeader>
        <Text style={uiStyles.muted}>Consulte os ajustes e medições registrados na sessão atual.</Text>
        <ActionButton label="ABRIR HISTÓRICO" secondary onPress={() => router.push('/history')} />
      </Card>
      <Card tone={state.apiState === 'ONLINE' ? 'success' : 'warning'}>
        <SectionHeader>SERVIDOR MANDACOR</SectionHeader>
        <StatusBadge online={state.apiState === 'ONLINE'} label={`SERVIDOR ${presentState(state.apiState)}`} />
        <Text style={uiStyles.muted}>URL atual: {state.baseUrl}</Text>
        <Text style={uiStyles.muted}>PC/backend: {splitUrl(state.baseUrl).host || 'não configurado'}</Text>
        <Text style={uiStyles.muted}>Versão: {state.serverVersion ?? 'desconhecida'} · API requerida: v1</Text>
        <Text style={uiStyles.muted}>Última verificação: {state.lastCheckedAt ? new Date(state.lastCheckedAt).toLocaleString('pt-BR') : 'nunca'}</Text>
        <Text style={uiStyles.muted}>Latência local: {state.latencyMs === null ? '—' : `${state.latencyMs} ms`}</Text>
        <Text style={styles.label}>Host / IP do computador</Text>
        <Field accessibilityLabel="Host da API" value={host} onChangeText={(value) => { setHost(value); setSaved(false); }} placeholder="192.168.1.11" />
        <Text style={styles.label}>Porta</Text>
        <Field accessibilityLabel="Porta da API" value={port} onChangeText={(value) => { setPort(value); setSaved(false); }} keyboardType="number-pad" placeholder="8000" />
        <ActionButton label="TESTAR E SALVAR" onPress={() => void save()} disabled={state.busy || !host.trim() || !port.trim()} />
        <ActionButton label="TESTAR SERVIDOR" onPress={() => void state.testApi()} disabled={state.busy} secondary />
        {saved && <Text style={styles.success}>Servidor testado e salvo.</Text>}
      </Card>
      <Card tone={state.instrumentState === 'ONLINE' ? 'success' : 'warning'}>
        <SectionHeader>ESPECTROFOTÔMETRO</SectionHeader>
        <StatusBadge online={state.instrumentState === 'ONLINE'} label={`BYK ${presentState(state.instrumentState)}`} />
        <Text style={uiStyles.muted}>Modelo: {state.instrument.instrument?.model ?? '—'}</Text>
        <Text style={uiStyles.muted}>Serial: {state.instrument.instrument?.serial ?? '—'}</Text>
        <Text style={uiStyles.muted}>IP atual: {state.instrument.instrument?.ip ?? '—'}</Text>
        {state.instrumentState === 'OFFLINE' && <Text style={uiStyles.muted}>Verifique se o aparelho está ligado, na mesma rede e acessível pelo PC.</Text>}
        {state.instrumentState === 'UNKNOWN' && <Text style={uiStyles.muted}>O estado do BYK é desconhecido porque o servidor ainda não respondeu.</Text>}
      </Card>
      <Card tone="info">
        <SectionHeader>DIAGNÓSTICO</SectionHeader>
        <Text style={uiStyles.muted}>App: {Constants.expoConfig?.version ?? '—'} · Build: {Constants.nativeBuildVersion ?? '—'}</Text>
        <Text style={uiStyles.muted}>Sessão: {state.currentSession?.session_id ?? 'nenhuma'}</Text>
        <Text style={uiStyles.muted}>Operação: {state.activeOperation?.operation_id ?? 'nenhuma'}</Text>
        <Text style={uiStyles.muted}>Pending: {state.pendingAdjustment?.adjustment_id ?? 'nenhum'}</Text>
        <Text style={uiStyles.muted}>Último código técnico: {state.errorTechnicalCode ?? 'nenhum'}</Text>
      </Card>
      <Card>
        <SectionHeader>CELULAR REAL</SectionHeader>
        <Text style={uiStyles.muted}>
          127.0.0.1 aponta para o próprio celular. Informe o IP LAN do computador que executa a FastAPI e inicie o backend com bind 0.0.0.0 em uma rede confiável.
        </Text>
        <Text style={uiStyles.muted}>Exemplo: http://192.168.1.11:8000 — o endereço é apenas ilustrativo e não está fixado no app.</Text>
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  label: { color: colors.textSecondary, fontSize: 14, fontWeight: '700' },
  success: { color: colors.success, fontSize: 14, fontWeight: '800' },
});
