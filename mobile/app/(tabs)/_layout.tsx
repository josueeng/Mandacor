import { Tabs } from 'expo-router';
import { ColorValue, Platform, Text, useWindowDimensions } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors } from '@/src/theme/tokens';

const MENU_LABELS: Record<string, string> = {
  index: 'INÍCIO',
  measure: 'MEDIR',
  results: 'RESULTADO',
  formulas: 'FÓRMULAS',
  settings: 'CONFIG',
};

function MenuLabel({ label, color, wide }: { label: string; color: ColorValue; wide: boolean }) {
  return (
    <Text
      adjustsFontSizeToFit
      allowFontScaling={false}
      minimumFontScale={0.68}
      numberOfLines={1}
      style={{
        color,
        fontSize: wide ? 12 : 10.5,
        fontWeight: '900',
        letterSpacing: wide ? 0.7 : 0,
        lineHeight: wide ? 16 : 14,
        paddingHorizontal: 1,
        textAlign: 'center',
        width: '100%',
      }}
    >
      {label}
    </Text>
  );
}

export default function TabLayout() {
  const insets = useSafeAreaInsets();
  const { width } = useWindowDimensions();
  const isWideScreen = width >= 700;
  const isDesktop = Platform.OS === 'web' && isWideScreen;
  const desktopMenuWidth = Math.min(720, width - 32);
  // Some Samsung devices report a zero/short bottom inset inside Expo Go even
  // while the three-button navigation bar is visible. Reserve its full height.
  const androidNavigationBar = Platform.OS === 'android' ? 48 : 10;
  const bottomSafeArea = Math.max(insets.bottom, androidNavigationBar);

  return (
    <Tabs
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarActiveBackgroundColor: colors.technicalSoft,
        tabBarActiveTintColor: colors.white,
        tabBarInactiveTintColor: '#C7D1DC',
        tabBarStyle: {
          alignSelf: 'center',
          backgroundColor: isDesktop ? colors.surfaceElevated : colors.surface,
          borderColor: isDesktop ? colors.borderStrong : colors.border,
          borderRadius: isDesktop ? 24 : 0,
          borderTopWidth: 1,
          borderWidth: isDesktop ? 1 : 0,
          bottom: isDesktop ? 18 : undefined,
          elevation: isDesktop ? 12 : 0,
          height: isDesktop ? 76 : (isWideScreen ? 68 : 64) + bottomSafeArea,
          left: isDesktop ? (width - desktopMenuWidth) / 2 : undefined,
          maxWidth: isDesktop ? desktopMenuWidth : isWideScreen ? 760 : 480,
          paddingBottom: isDesktop ? 8 : bottomSafeArea,
          paddingHorizontal: isDesktop ? 8 : isWideScreen ? 12 : 2,
          paddingTop: 8,
          position: isDesktop ? 'absolute' : 'relative',
          shadowColor: isDesktop ? '#05080C' : 'transparent',
          shadowOffset: { width: 0, height: 10 },
          shadowOpacity: isDesktop ? 0.32 : 0,
          shadowRadius: isDesktop ? 22 : 0,
          width: isDesktop ? desktopMenuWidth : '100%',
        },
        tabBarItemStyle: {
          borderRadius: isDesktop ? 16 : 10,
          marginHorizontal: isWideScreen ? 4 : 1,
          minHeight: isDesktop ? 58 : isWideScreen ? 58 : 54,
          paddingHorizontal: isDesktop ? 5 : 1,
        },
        tabBarLabel: ({ color }) => (
          <MenuLabel
            color={color}
            label={MENU_LABELS[route.name] ?? route.name.toUpperCase()}
            wide={isWideScreen}
          />
        ),
      })}>
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
      <Tabs.Screen name="history" options={{ href: null }} />
      <Tabs.Screen name="formulas" options={{ title: 'FÓRMULAS', tabBarIcon: ({ color }) => <Text style={{ color, fontSize: 18 }}>≣</Text> }} />
      <Tabs.Screen name="settings" options={{ title: 'CONFIG', tabBarIcon: ({ color }) => <Text style={{ color, fontSize: 18 }}>⚙</Text> }} />
    </Tabs>
  );
}
