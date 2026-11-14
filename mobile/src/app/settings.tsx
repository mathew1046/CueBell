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
import { useLanguage } from '../lib/i18n';

const modes: { value: ThemeMode; label: string; icon: string }[] = [
  { value: 'system', label: 'Auto', icon: 'theme-light-dark' },
  { value: 'light', label: 'Light', icon: 'white-balance-sunny' },
  { value: 'dark', label: 'Dark', icon: 'weather-night' },
];

export default function Settings() {
  const { t } = useLanguage();
  const { section } = useLocalSearchParams<{ section?: string }>();
  const theme = useAppTheme();
  const insets = useSafeAreaInsets();
  const app = useCueBell();
  const { mode, setMode } = useThemeMode();
  const [spokenAlerts, setSpokenAlerts] = useState(() => Listener.spokenAlertsEnabled());
  const heading = (text: string) => <Text variant="titleMedium" accessibilityRole="header"
    style={{ color: theme.colors.onSurfaceVariant }}>{t(text)}</Text>;
  const accessibility = <>
    {heading('Accessibility')}
    <SoftCard style={styles.group}>
      <View style={styles.switchRow}>
        <Text variant="titleMedium" style={[styles.flex, { color: theme.colors.onSurface }]}>{t('Spoken alerts')}</Text>
        <Switch value={spokenAlerts} accessibilityLabel={t('Spoken alerts')} hitSlop={12}
          onValueChange={enabled => { Listener.setSpokenAlertsEnabled(enabled); setSpokenAlerts(enabled); }} />
      </View>
    </SoftCard>
  </>;

  return <View style={[styles.root, { backgroundColor: theme.colors.background, paddingTop: insets.top }]}>
    <ScreenHeader title={t('Settings')} status={{ tone: app.tone, icon: app.statusIcon, label: app.statusLabel }} />
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
            accessibilityLabel={t('{mode} theme', { mode: t(item.label) })} accessibilityState={{ selected, checked: selected }}
            style={[styles.mode, { backgroundColor: selected ? theme.colors.primary : theme.colors.surface,
              boxShadow: selected ? theme.shadow.hero : theme.shadow.soft }]}>
            <Icon source={selected ? 'check-circle' : item.icon} size={28} color={selected ? theme.colors.onPrimary : theme.colors.onSurface} />
            <Text variant="titleMedium" style={{ color: selected ? theme.colors.onPrimary : theme.colors.onSurface }}>{t(item.label)}</Text>
          </Pressable>;
        })}
      </View>

      {section !== 'accessibility' && accessibility}

      {heading('Listening')}
      <SoftCard style={styles.group}>
        <View style={styles.switchRow}>
          <View style={styles.flex}>
            <Text variant="titleMedium" style={{ color: theme.colors.onSurface }}>{t('Noise reduction')}</Text>
            <Text variant="bodyMedium" style={{ color: theme.colors.onSurfaceVariant }}>{app.noiseReductionMode === 'gtcrn' ? t('On') : t('Off')}</Text>
          </View>
          <Switch value={app.noiseReductionMode === 'gtcrn'} disabled={app.noiseReductionLocked}
            accessibilityLabel={t('Noise reduction')} hitSlop={12}
            onValueChange={enabled => app.setNoiseReductionMode(enabled ? 'gtcrn' : 'off')} />
        </View>
        <Text variant="bodyMedium" style={{ color: theme.colors.onSurfaceVariant }}>{t('Experimental · on-device (GTCRN). May affect speech.')}</Text>
        {app.noiseReductionFallback && <Text variant="bodyMedium" accessibilityLiveRegion="polite" style={{ color: theme.colors.onSurfaceVariant }}>
          {t('Noise reduction is unavailable. Listening continues without it.')}</Text>}
        {app.noiseReductionLocked && !app.booting && <Text variant="bodyMedium" style={{ color: theme.colors.onSurfaceVariant }}>
          {t('Stop setup or pause listening to change this.')}</Text>}
        {!!app.noiseReductionStorageError && <Text variant="bodyMedium" accessibilityLiveRegion="polite"
          style={{ color: theme.colors.error }}>{app.noiseReductionStorageError}</Text>}
        {app.activeRule ? <>
          <Text variant="bodyLarge" style={{ color: theme.colors.onSurface }}
            accessibilityLabel={t('Listening for: {task}', { task: app.activeRule.task?.summary ?? spell(app.activeRule.token ?? '') })}>{t('Listening for: {task}', { task: app.activeRule.task?.summary ?? app.activeRule.token ?? '' })}</Text>
          {app.native.running ? <Button mode="contained-tonal" icon="pause" contentStyle={actionStyles.big} disabled={app.busy}
            onPress={app.pause}>{t('Pause')}</Button> :
            <Button mode="contained" icon="microphone" contentStyle={actionStyles.big} disabled={app.busy || !app.consent}
              onPress={app.resume}>{t('Start Listening')}</Button>}
          <Button mode="outlined" icon="stop" textColor={theme.colors.error} style={{ borderColor: theme.colors.error, borderWidth: 2 }}
            contentStyle={actionStyles.action} disabled={app.busy} onPress={app.stop}
            accessibilityHint={t('Stops the microphone and clears your listening task and history from this phone')}>{t('Stop')}</Button>
        </> : <Text variant="bodyLarge" style={{ color: theme.colors.onSurfaceVariant }}>{t('No listening task is active.')}</Text>}
      </SoftCard>

      {heading('Phone')}
      <Pressable onPress={() => void Linking.openSettings()} accessibilityRole="button" accessibilityLabel={t('Android permissions')}
        accessibilityHint={t('Opens Android settings for microphone and notifications')}
        style={({ pressed }) => [styles.row, { backgroundColor: theme.colors.surface, boxShadow: pressed ? theme.shadow.inset : theme.shadow.soft }]}>
        <Icon source="cellphone-cog" size={28} color={theme.colors.onSurface} />
        <Text variant="titleMedium" style={[styles.flex, { color: theme.colors.onSurface }]}>{t('Android permissions')}</Text>
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
  mode: { flex: 1, minHeight: 96, padding: 8, borderRadius: 24, alignItems: 'center', justifyContent: 'center', gap: 8 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 14, minHeight: 72, borderRadius: 24, paddingHorizontal: 20 },
});
