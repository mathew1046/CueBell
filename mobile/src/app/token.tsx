import { useIsFocused, useRouter } from 'expo-router';
import { useEffect } from 'react';
import { AccessibilityInfo, Animated, KeyboardAvoidingView, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { ActivityIndicator, Button, Icon, Text, TextInput } from 'react-native-paper';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { ConsentCard, ErrorBanner } from '../components/app';
import { actionStyles, Notice, ScreenHeader, usePulse } from '../components/ui';
import { haptic, useReduceMotion } from '../lib/a11y';
import { useCueBell } from '../lib/cuebell';
import { useLanguage } from '../lib/i18n';
import { useAppTheme } from '../lib/theme';

export default function TokenScreen() {
  const { t } = useLanguage();
  const theme = useAppTheme();
  const insets = useSafeAreaInsets();
  const reduceMotion = useReduceMotion();
  const router = useRouter();
  const focused = useIsFocused();
  const app = useCueBell();
  const pulse = usePulse(app.capturing && !reduceMotion, 800);

  useEffect(() => {
    if (!app.proposal || !focused) return;
    if (router.canGoBack()) router.back();
    else router.replace('/');
  }, [app.proposal, focused, router]);

  return <KeyboardAvoidingView style={[styles.root, { backgroundColor: theme.colors.background }]} behavior="padding">
    <View style={{ paddingTop: insets.top }}>
      <ScreenHeader title={t('Listening task')} status={{ tone: app.tone, icon: app.statusIcon, label: app.statusLabel }} />
    </View>
    <ScrollView keyboardShouldPersistTaps="handled"
      contentContainerStyle={[styles.content, { paddingBottom: Math.max(insets.bottom, 24) + 24 }]}>
      <ErrorBanner />
      {!app.native.running && !app.consent && <ConsentCard />}

      {app.capturing ? <View style={styles.capturing} accessible accessibilityLabel={t('Microphone on. Describe what to listen for. Short pauses are OK.')}>
        <View style={styles.micWrap}>
          <Animated.View style={[styles.micHalo, { backgroundColor: theme.colors.surfaceVariant, opacity: pulse }]} />
          <View style={[styles.mic, { backgroundColor: theme.colors.primary, boxShadow: theme.shadow.hero }]}>
            <Icon source="microphone" size={52} color={theme.colors.onPrimary} />
          </View>
        </View>
        <Text variant="headlineSmall" style={[styles.center, { color: theme.colors.onSurface }]}>{t('Describe what to listen for')}</Text>
        <Text variant="bodyLarge" style={[styles.center, { color: theme.colors.onSurfaceVariant }]}>{t('Short pauses are OK.')}</Text>
      </View> :
        <Pressable onPress={app.consent ? app.speak : () => {
          haptic.stopped(); AccessibilityInfo.announceForAccessibility(t('First tick Allow audio and text processing, above.'));
        }} disabled={app.busy} accessibilityRole="button"
          accessibilityLabel={app.consent ? t('Speak') : t('Speak. Tick Allow above first.')}
          accessibilityHint={t('For example: alert me when train 14922 arrives. Short pauses are OK.')}
          accessibilityState={{ disabled: app.busy }}
          style={({ pressed }) => [styles.speak, { backgroundColor: theme.colors.primary, boxShadow: theme.shadow.hero,
            transform: [{ scale: pressed ? 0.98 : 1 }] }]}>
          <Icon source="microphone" size={40} color={theme.colors.onPrimary} />
          <Text style={[styles.speakLabel, { color: theme.colors.onPrimary }]}>{t('Speak')}</Text>
        </Pressable>}
      {app.capturing && <Button mode="outlined" icon="stop" contentStyle={actionStyles.big} textColor={theme.colors.onSurface}
        style={{ borderColor: theme.colors.onSurface, borderWidth: 2 }} onPress={app.cancelCapture}>{t('Cancel')}</Button>}

      <View style={styles.dividerRow} importantForAccessibility="no-hide-descendants">
        <View style={[styles.rule, { backgroundColor: theme.colors.outlineVariant }]} />
        <Text variant="labelLarge" style={{ color: theme.colors.onSurfaceVariant }}>{t('or type')}</Text>
        <View style={[styles.rule, { backgroundColor: theme.colors.outlineVariant }]} />
      </View>

      <Text variant="bodyLarge" style={{ color: theme.colors.onSurfaceVariant }}>{t('Tell CueBell who or what to listen for, and what event should trigger an alert.')}</Text>
      <TextInput mode="outlined" label={t('What should I listen for?')} multiline value={app.request} onChangeText={app.editRequest}
        placeholder={t('Alert me when train 14922 arrives.')} outlineStyle={styles.outline} outlineColor={theme.colors.outline}
        activeOutlineColor={theme.colors.onSurface} style={[styles.input, { backgroundColor: theme.colors.surface }]}
        maxLength={1500} editable={!app.busy && !app.native.running} />
      <Button mode="contained" icon="arrow-right" contentStyle={[actionStyles.big, styles.reverse]} style={styles.radius}
        disabled={!app.consent || app.busy || app.native.running || !app.request.trim()}
        onPress={() => app.analyze(app.request)}>{t('Continue')}</Button>
      {app.busy && !app.capturing && <ActivityIndicator color={theme.colors.onSurface} accessibilityLabel={t('Understanding your request')} />}
      {app.clarification !== '' && <Notice tone="warn" icon="help-circle" live="polite">{app.clarification}</Notice>}
    </ScrollView>
  </KeyboardAvoidingView>;
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  content: { paddingHorizontal: 24, paddingTop: 8, gap: 24, maxWidth: 560, width: '100%', alignSelf: 'center' },
  center: { textAlign: 'center' },
  speak: { minHeight: 112, borderRadius: 32, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 14 },
  speakLabel: { fontSize: 30, lineHeight: 36, fontWeight: '700' },
  capturing: { alignItems: 'center', gap: 8, paddingVertical: 8 },
  micWrap: { width: 168, height: 168, alignItems: 'center', justifyContent: 'center' },
  micHalo: { position: 'absolute', width: 168, height: 168, borderRadius: 84 },
  mic: { width: 112, height: 112, borderRadius: 40, alignItems: 'center', justifyContent: 'center' },
  dividerRow: { flexDirection: 'row', alignItems: 'center', gap: 12 }, rule: { flex: 1, height: 1 },
  input: { minHeight: 120, fontSize: 20 }, outline: { borderRadius: 20, borderWidth: 2 },
  reverse: { flexDirection: 'row-reverse' }, radius: { borderRadius: 20 },
});
