import { StyleSheet, View } from 'react-native';
import { Button, Checkbox, Icon, Text } from 'react-native-paper';
import { useCueBell } from '../lib/cuebell';
import { useLanguage } from '../lib/i18n';
import { useAppTheme } from '../lib/theme';
import { actionStyles, SoftCard } from './ui';
import { PermissionHelp } from './permission-help';

export function ErrorBanner() {
  const { t } = useLanguage();
  const theme = useAppTheme();
  const app = useCueBell();
  if (!app.error) return null;
  return <View style={[styles.error, { backgroundColor: theme.colors.errorContainer, borderColor: theme.colors.error }]}>
    <View style={styles.inline}>
      <Icon source="alert-circle" size={26} color={theme.colors.onErrorContainer} />
      <Text variant="bodyLarge" accessibilityRole="alert" accessibilityLiveRegion="assertive"
         style={[styles.flex, { color: theme.colors.onErrorContainer }]}>{app.error}</Text>
    </View>
    <View style={styles.row}>
      {app.permissionError && <PermissionHelp />}
      <Button mode="outlined" textColor={theme.colors.onErrorContainer} contentStyle={actionStyles.action}
        style={{ borderColor: theme.colors.onErrorContainer }} onPress={app.clearError} accessibilityLabel={t('Dismiss error')}>{t('Dismiss')}</Button>
    </View>
  </View>;
}

/** Explicit processing consent with named recipients. Required before Speak, Continue or Start Listening. */
export function ConsentCard() {
  const { t } = useLanguage();
  const theme = useAppTheme();
  const app = useCueBell();
  return <SoftCard style={styles.consent}>
    <Checkbox.Item label={t('Allow audio & text processing')} status={app.consent ? 'checked' : 'unchecked'}
      onPress={app.toggleConsent} position="leading" disabled={app.native.running}
      style={styles.checkbox} labelStyle={[styles.checkboxLabel, { color: theme.colors.onSurface }]} />
    <View style={styles.inline}>
      <Icon source="shield-lock-outline" size={20} color={theme.colors.onSurfaceVariant} />
      <Text variant="bodyMedium" style={[styles.flex, { color: theme.colors.onSurfaceVariant }]}>
        {app.native.running ? t('Allowed. Pause listening to change this.') : t('Audio goes to Gnani. Text goes to OpenAI.')}</Text>
    </View>
  </SoftCard>;
}

const styles = StyleSheet.create({
  flex: { flex: 1, gap: 4 }, row: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  inline: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
  error: { padding: 16, gap: 12, borderRadius: 20, borderWidth: 2 },
  consent: { paddingHorizontal: 12, paddingTop: 4, paddingBottom: 16, gap: 4 },
  checkbox: { paddingHorizontal: 0, paddingVertical: 8, minHeight: 56 },
  checkboxLabel: { fontSize: 18, fontWeight: '600', textAlign: 'left' },
});
