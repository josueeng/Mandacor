import { Tabs } from 'expo-router';
import { Text } from 'react-native';

import { colors } from '@/src/theme/tokens';

export default function TabLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.action,
        tabBarInactiveTintColor: colors.textSecondary,
        tabBarStyle: {
          alignSelf: 'center',
          backgroundColor: colors.surface,
          borderTopColor: colors.border,
          borderTopWidth: 1,
          height: 70,
          maxWidth: 480,
          paddingTop: 7,
          width: '100%',
        },
        tabBarItemStyle: { borderRadius: 10, marginHorizontal: 2 },
        tabBarLabelStyle: { fontSize: 9, fontWeight: '900', letterSpacing: 0.4, paddingBottom: 7 },
      }}>
      <Tabs.Screen
        name="index"
        options={{
          title: 'INÍCIO',
          tabBarIcon: ({ color }) => <Text style={{ color, fontSize: 19 }}>⌂</Text>,
        }}
      />
      <Tabs.Screen
        name="measure"
        options={{
          title: 'MEDIR',
          tabBarIcon: ({ color }) => <Text style={{ color, fontSize: 18 }}>◎</Text>,
        }}
      />
      <Tabs.Screen name="results" options={{ title: 'RESULTADO', tabBarIcon: ({ color }) => <Text style={{ color, fontSize: 18 }}>Δ</Text> }} />
      <Tabs.Screen name="history" options={{ title: 'HISTÓRICO', tabBarIcon: ({ color }) => <Text style={{ color, fontSize: 18 }}>↻</Text> }} />
      <Tabs.Screen name="settings" options={{ title: 'CONFIG', tabBarIcon: ({ color }) => <Text style={{ color, fontSize: 18 }}>⚙</Text> }} />
    </Tabs>
  );
}
