import { router } from 'expo-router';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Text } from 'react-native';

import { MandacorApiClient } from '@/src/api/client';
import { friendlyError } from '@/src/api/errors';
import { ActionButton, Card, EmptyState, ErrorNotice, Screen, ScreenHeader, TechnicalRow } from '@/src/components/ui';
import { presentState } from '@/src/presentation/format';
import { useMandacor } from '@/src/state/AppContext';
import { Adjustment } from '@/src/types/api';

export default function HistoryScreen() {
  const app = useMandacor();
  const client = useMemo(() => new MandacorApiClient(app.baseUrl), [app.baseUrl]);
  const [items, setItems] = useState<Adjustment[]>([]);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    if (!app.currentSession) return;
    try {
      setItems(await client.listAdjustments(app.currentSession.session_id));
      setError(null);
    } catch (caught) {
      setError(friendlyError(caught));
    }
  }, [app.currentSession, client]);
  useEffect(() => { void load(); }, [load]);

  return <Screen>
    <ScreenHeader
      eyebrow="RASTREABILIDADE"
      title="Histórico da sessão"
      subtitle="Ajustes registrados em ordem cronológica, com pigmentos, massas e leituras preservados."
    />
    <ErrorNotice message={error} />
    {!app.currentSession && <EmptyState>Nenhuma sessão disponível.</EmptyState>}
    {items.map((item, index) => <Card key={item.adjustment_id} tone={item.lifecycle === 'COMPLETED' ? 'success' : 'info'}>
      <Text style={{ color: '#F4F7FA', fontSize: 16, fontWeight: '900' }}>AJUSTE {items.length - index}</Text>
      <TechnicalRow label="Estado" value={presentState(item.lifecycle)} />
      <TechnicalRow label="Cadeia" value={`#${item.target_measurement_id} → #${item.before_measurement_id} → ${item.after_measurement_id ? `#${item.after_measurement_id}` : 'AFTER pendente'}`} />
      <TechnicalRow label="Criado" value={new Date(item.created_at).toLocaleString('pt-BR')} />
      <TechnicalRow label="Componentes" value={item.components.map((value) => `${value.pigment_code} ${value.quantity_g} g`).join(' + ')} />
      <ActionButton label="ABRIR REGISTRO" secondary onPress={() => router.push(`../adjustment?id=${item.adjustment_id}`)} />
    </Card>)}
    {app.currentSession && !items.length && <EmptyState>Nenhum ajuste registrado nesta sessão.</EmptyState>}
    <ActionButton label="ATUALIZAR HISTÓRICO" secondary onPress={() => void load()} />
  </Screen>;
}
