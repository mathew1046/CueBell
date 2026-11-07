import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Linking, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { Button, Icon, Switch, Text } from 'react-native-paper';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Listener from '../../modules/queue-listener';
import { ConsentCard, ErrorBanner } from '../components/app';
import { actionStyles, ScreenHeader, SoftCard } from '../components/ui';
import { spell } from '../lib/a11y';
import { useCueBell } from '../lib/cuebell';
import { useAppTheme } from '../lib/theme';
import { ThemeMode, useThemeMode } from '../lib/themeMode';

const modes: { value: ThemeMode; label: string; icon: string }[] = [
  { value: 'system', label: 'Auto', icon: 'theme-light-dark' },
  { value: 'light', label: 'Light', icon: 'white-balance-sunny' },
  { value: 'dark', label: 'Dark', icon: 'weather-night' },
];

export default function Settings() {
  const { section } = useLocalSearchParams<{ section?: string }>();
  const theme = useAppTheme();
  const insets = useSafeAreaInsets();
  const app = useCueBell();
  const { mode, setMode } = useThemeMode();
  const [spokenAlerts, setSpokenAlerts] = useState(() => Listener.spokenAlertsEnabled());
  const heading = (text: string) => <Text variant="titleMedium" accessibilityRole="header"
    style={{ color: theme.colors.onSurfaceVariant }}>{text}</Text>;
  const accessibility = <>
    {heading('Accessibility')}
    <SoftCard style={styles.group}>
      <View style={styles.switchRow}>
        <Text variant="titleMedium" style={[styles.flex, { color: theme.colors.onSurface }]}>Spoken token alerts</Text>
        <Switch value={spokenAlerts} accessibilityLabel="Spoken token alerts" hitSlop={12}
          onValueChange={enabled => { Listener.setSpokenAlertsEnabled(enabled); setSpokenAlerts(enabled); }} />
      </View>
      <Text variant="bodyMedium" style={{ color: theme.colors.onSurfaceVariant }}>
        Uses an installed offline Android voice when your alert includes sound. TalkBack reads alerts when enabled.
      </Text>
    </SoftCard>
  </>;

  return <View style={[styles.root, { backgroundColor: theme.colors.background, paddingTop: insets.top }]}>
    <ScreenHeader title="Settings" status={{ tone: app.tone, icon: app.statusIcon, label: app.statusLabel }} />
    <ScrollView contentContainerStyle={[styles.content, { paddingBottom: Math.max(insets.bottom, 24) + 24 }]}>
      <ErrorBanner />
      {section === 'accessibility' && accessibility}

      {heading('Processing')}
      <ConsentCard />

      {heading('Appearance')}
      <View style={styles.modes} accessibilityRole="radiogroup">
        {modes.map(item => {
          const selected = mode === item.value;
          return <Pressable key={item.value} onPress={() => setMode(item.value)} accessibilityRole="radio"
            accessibilityLabel={`${item.label} theme`} accessibilityState={{ selected, checked: selected }}
            style={[styles.mode, { backgroundColor: selected ? theme.colors.primary : theme.colors.surface,
              boxShadow: selected ? theme.shadow.hero : theme.shadow.soft }]}>
            <Icon source={selected ? 'check-circle' : item.icon} size={28} color={selected ? theme.colors.onPrimary : theme.colors.onSurface} />
            <Text variant="titleMedium" style={{ color: selected ? theme.colors.onPrimary : theme.colors.onSurface }}>{item.label}</Text>
          </Pressable>;
        })}
      </View>

      {section !== 'accessibility' && accessibility}

      {heading('Listening')}
      <SoftCard style={styles.group}>
        {app.activeRule ? <>
          <Text variant="bodyLarge" style={{ color: theme.colors.onSurface }}
            accessibilityLabel={`Watching token ${spell(app.activeRule.token)}`}>{`Watching token ${app.activeRule.token}`}</Text>
          {app.native.running ? <Button mode="contained-tonal" icon="pause" contentStyle={actionStyles.big} disabled={app.busy}
            onPress={app.pause}>Pause</Button> :
            <Button mode="contained" icon="microphone" contentStyle={actionStyles.big} disabled={app.busy || !app.consent}
              onPress={app.resume}>Start Listening</Button>}
          <Button mode="outlined" icon="stop" textColor={theme.colors.error} style={{ borderColor: theme.colors.error, borderWidth: 2 }}
            contentStyle={actionStyles.action} disabled={app.busy} onPress={app.stop}
            accessibilityHint="Stops the microphone and clears your token and history from this phone">Stop</Button>
          <Text variant="bodyMedium" style={{ color: theme.colors.onSurfaceVariant }}>Stop also clears your token and history.</Text>
        </> : <Text variant="bodyLarge" style={{ color: theme.colors.onSurfaceVariant }}>No token is being watched.</Text>}
      </SoftCard>

      {heading('Phone')}
      <Pressable onPress={() => void Linking.openSettings()} accessibilityRole="button" accessibilityLabel="Android permissions"
        accessibilityHint="Opens Android settings for microphone and notifications"
        style={({ pressed }) => [styles.row, { backgroundColor: theme.colors.surface, boxShadow: pressed ? theme.shadow.inset : theme.shadow.soft }]}>
        <Icon source="cellphone-cog" size={28} color={theme.colors.onSurface} />
        <Text variant="titleMedium" style={[styles.flex, { color: theme.colors.onSurface }]}>Android permissions</Text>
        <Icon source="chevron-right" size={28} color={theme.colors.onSurfaceVariant} />
      </Pressable>
    </ScrollView>
  </View>;
}

const styles = StyleSheet.create({
  root: { flex: 1 }, flex: { flex: 1 },
  content: { paddingHorizontal: 24, paddingTop: 8, gap: 16, maxWidth: 560, width: '100%', alignSelf: 'center' },
  group: { gap: 14 },
  switchRow: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 48 },
  modes: { flexDirection: 'row', gap: 12 },
  mode: { flex: 1, minHeight: 96, borderRadius: 24, alignItems: 'center', justifyContent: 'center', gap: 8 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 14, minHeight: 72, borderRadius: 24, paddingHorizontal: 20 },
});
