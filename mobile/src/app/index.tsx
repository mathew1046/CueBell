import { useIsFocused, useRouter } from 'expo-router';
import { useState } from 'react';
import { AccessibilityInfo, ActivityIndicator, Image, Pressable, ScrollView, StyleSheet, View, useWindowDimensions } from 'react-native';
import { Button, Icon, Text } from 'react-native-paper';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { ConsentCard, ErrorBanner } from '../components/app';
import { ListeningWaveform, LiveTranscription } from '../components/listening';
import { LanguageMenu } from '../components/language-menu';
import { AlertCard, NavTile, Notice, SoftCard, SoftIconButton } from '../components/ui';
import { spell, useReduceMotion } from '../lib/a11y';
import { useCueBell } from '../lib/cuebell';
import { useLanguage } from '../lib/i18n';
import { useAppTheme } from '../lib/theme';

export default function Home() {
  const { t, language } = useLanguage();
  const theme = useAppTheme();
  const insets = useSafeAreaInsets();
  const reduceMotion = useReduceMotion();
  const router = useRouter();
  const focused = useIsFocused();
  const { width, fontScale } = useWindowDimensions();
  const [consentRequested, setConsentRequested] = useState(false);
  const [captionsOpen, setCaptionsOpen] = useState(false);
  const app = useCueBell();
  const { activeRule, proposal, native, listening, capturing, captureMode, consent, busy, phase } = app;
  const token = (proposal?.intent ?? activeRule)?.token;
  const task = (proposal?.intent ?? activeRule)?.task;
  const hasTask = !!(task || token);
  const captureInProgress = phase !== 'IDLE' && phase !== 'ERROR';
  const showRequest = captureInProgress && captureMode === 'request';
  const showTranscript = showRequest || (captureInProgress && captionsOpen);
  const stopping = phase === 'STOPPING';
  const canStop = (native.running || busy) && !stopping;
  const status = listening && showRequest ? t('Describe what to listen for') : app.statusLabel;
  const heroSize = Math.min(320, Math.round(width * 2 / 3));
  const heroSpace = Math.min(52, Math.round(width * 0.12));
  const headerTop = Math.max(8, Math.min(60, Math.round(width * 0.135)) - insets.top);
  const largeTokenLayout = !!task || fontScale >= 1.5 || language !== 'en';
  const background = theme.dark ? theme.colors.background : '#F8F5F4';
  const shortcutStyle = [styles.shortcut, { backgroundColor: theme.dark ? theme.colors.surfaceVariant : '#EFEAE8' }];
  const editToken = () => {
    app.clearProposal();
    router.push('/token');
  };
  const label = canStop ? t('Stop Listening') :
    stopping ? t('Stopping...') : phase === 'ERROR' ? t('Retry Listening') : t('Start Listening');
  const press = () => {
    if (canStop) {
      return captureMode === 'request' || busy ? app.cancelCapture() : app.pause();
    }
    if (!consent) {
      setConsentRequested(true);
      AccessibilityInfo.announceForAccessibility(t('Allow audio and text processing below before starting.'));
      return;
    }
    setConsentRequested(false);
    if (!hasTask) {
      return app.speak();
    }
    if (proposal) return app.confirm();
    app.resume();
  };

  return <View style={[styles.root, { backgroundColor: background, paddingTop: insets.top }]}>
    <ScrollView keyboardShouldPersistTaps="handled"
      contentContainerStyle={[styles.content, { paddingTop: headerTop, paddingBottom: insets.bottom + 20 }]}>
      <View style={[styles.header, fontScale >= 1.5 && width < 420 && styles.headerWrap]}>
        <View style={styles.brand}>
          <View importantForAccessibility="no-hide-descendants">
            <Image source={require('../../assets/cuebell-mark.png')} resizeMode="contain"
              style={[styles.brandMark, theme.dark && { tintColor: theme.colors.onSurface }]} />
          </View>
          <View style={styles.brandCopy}>
            <Text variant="headlineSmall" accessibilityRole="header" style={[styles.brandTitle, { color: theme.colors.onSurface }]}>CueBell</Text>
          </View>
        </View>
        <View style={styles.shortcuts}>
          <LanguageMenu style={shortcutStyle} />
          <SoftIconButton icon="human" label={t('Accessibility settings')} style={shortcutStyle}
            onPress={() => router.push({ pathname: '/settings', params: { section: 'accessibility' } })} />
        </View>
      </View>

      {app.booting ? <ActivityIndicator size="large" style={styles.restoring}
        accessibilityLabel={t('Restoring your session')} /> : <>
        <View style={[styles.heroGroup, { marginVertical: heroSpace }]}>
          <Pressable testID="listening-control" accessibilityRole="button" accessibilityLabel={label}
            accessibilityHint={canStop ? t('Turns off the microphone. Recent captions are in History.') :
              hasTask ? app.statusLabel : t('Describe what to listen for. Use the pencil to type your request.')}
            accessibilityState={{ disabled: stopping, busy: busy && !canStop }}
            disabled={stopping} onPress={press}
            style={({ pressed }) => [styles.hero, {
              width: heroSize, minHeight: heroSize, borderRadius: Math.round(heroSize * 0.29),
              backgroundColor: theme.dark ? theme.colors.primary : '#323234', boxShadow: theme.shadow.hero,
              transform: [{ scale: pressed && !reduceMotion ? 0.98 : 1 }],
            }]}>
            <View pointerEvents="none" importantForAccessibility="no-hide-descendants" style={styles.heroContent}>
              {captureInProgress ? <ListeningWaveform
                animate={focused && listening && !reduceMotion && !app.takeover}
                color={theme.colors.onPrimary} height={Math.round(heroSize * 0.28)} /> :
                <Icon source={capturing ? app.statusIcon : 'microphone'} size={Math.round(heroSize * 0.28)} color={theme.colors.onPrimary} />}
              <Text style={[styles.heroTitle, { color: theme.colors.onPrimary }]}>{label}</Text>
              {captureInProgress && status !== label &&
                <Text style={[styles.heroStatus, { color: theme.colors.onPrimary }]}>{status}</Text>}
              <View style={[styles.heroAction, { backgroundColor: theme.colors.onPrimary }]}>
                {busy && !canStop ? <ActivityIndicator color={theme.colors.primary} /> :
                  <Icon source={canStop ? 'stop' : 'play'} size={29} color={theme.colors.primary} />}
              </View>
            </View>
          </Pressable>
          {captureInProgress && !showRequest && <Button mode="text"
            icon={captionsOpen ? 'chevron-up' : 'chevron-down'}
            accessibilityState={{ expanded: captionsOpen }} contentStyle={{ minHeight: 48 }}
            onPress={() => setCaptionsOpen(!captionsOpen)}>{t('Live captions')}</Button>}
          {showTranscript && <LiveTranscription events={app.events}
            mode={showRequest ? 'request' : 'monitor'} listening={listening} />}
          {!!app.statusDetail && <Text variant="bodyMedium" style={{ color: theme.colors.onSurfaceVariant }}>{app.statusDetail}</Text>}
          {consentRequested && !consent && !native.running && <ConsentCard />}
          <ErrorBanner />
          {!captureInProgress && !!app.clarification &&
            <Notice tone="warn" icon="help-circle" live="polite">{app.clarification}</Notice>}
          {showTranscript && !showRequest && app.latestUnclear &&
            <Notice tone="warn" icon="help-circle">{t('Unclear announcement. Check the display.')}</Notice>}
        </View>

        <SoftCard style={styles.tokenCard}>
          <View style={styles.tokenRow}>
            <View style={[styles.tokenReadout, largeTokenLayout && styles.tokenReadoutLarge]} accessible accessibilityLabel={hasTask ?
              t('{label}, {task}', { label: t('Listening task'), task: task?.summary ?? spell(token ?? '') }) : t('Listening task, not set')}>
              <View style={styles.tokenLabel}>
                <Icon source="ear-hearing" size={38} color={theme.colors.onSurface} />
              </View>
              {!largeTokenLayout && <View style={[styles.divider, { backgroundColor: theme.colors.outlineVariant }]} />}
              <Text style={[styles.tokenValue, (!token || !!task) && styles.noToken, largeTokenLayout && styles.tokenValueLarge,
                { color: theme.colors.onSurface }]}>
                {task?.summary ?? token ?? t('What should I listen for?')}
              </Text>
            </View>
            <SoftIconButton icon="pencil-outline" label={hasTask ? t('Change listening task') : t('Set a listening task')}
              style={styles.shortcut} disabled={native.running || busy} onPress={editToken} />
          </View>
        </SoftCard>

        {app.outstanding.length > 0 && <View style={styles.alerts}>
          {app.outstanding.map(alert => <AlertCard key={alert.id} alert={alert} busy={busy}
            onSeen={() => app.acknowledge(alert.id)} onOpen={() => app.showAlert(alert.id)} />)}
        </View>}

        <View style={styles.tiles}>
          <NavTile icon="history" label={t('History')} onPress={() => router.push('/history')} />
          <NavTile icon="cog-outline" label={t('Settings')} onPress={() => router.push('/settings')} />
          <NavTile icon="help-circle-outline" label={t('Help')} onPress={() => router.push('/help')} />
        </View>
      </>}
    </ScrollView>
  </View>;
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  content: { width: '100%', maxWidth: 560, alignSelf: 'center', paddingHorizontal: 16 },
  header: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 8 },
  headerWrap: { flexWrap: 'wrap', justifyContent: 'flex-end' },
  brand: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 12 },
  brandMark: { width: 44, height: 48 },
  brandCopy: { flex: 1, gap: 1 },
  brandTitle: { fontWeight: '700' },
  shortcuts: { flexDirection: 'row', gap: 10 },
  shortcut: { width: 48, height: 48, borderRadius: 16 },
  restoring: { marginTop: 48 },
  heroGroup: { gap: 14 },
  hero: { alignSelf: 'center', paddingHorizontal: 18, paddingVertical: 24, justifyContent: 'center' },
  heroContent: { alignItems: 'center', gap: 11 },
  heroTitle: { width: '100%', fontSize: 26, lineHeight: 36, fontWeight: '700', textAlign: 'center' },
  heroStatus: { width: '100%', fontSize: 14, lineHeight: 22, textAlign: 'center' },
  heroAction: { width: 50, height: 50, borderRadius: 25, alignItems: 'center', justifyContent: 'center', marginTop: 2 },
  tokenCard: { paddingHorizontal: 20, paddingVertical: 14, borderRadius: 28, gap: 12 },
  tokenRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  tokenReadout: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 14 },
  tokenReadoutLarge: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  tokenLabel: { flexDirection: 'row', alignItems: 'center', alignSelf: 'stretch', flexShrink: 1, gap: 10 },
  divider: { width: 1, height: 40 },
  tokenValue: { flex: 1, fontSize: 46, lineHeight: 56, fontWeight: '800', fontVariant: ['tabular-nums'], textAlign: 'center' },
  tokenValueLarge: { flex: 1, textAlign: 'left' },
  noToken: { fontSize: 18, lineHeight: 25, fontWeight: '600' },
  alerts: { gap: 12, marginTop: 24 },
  tiles: { flexDirection: 'row', gap: 14, marginTop: 34 },
});
