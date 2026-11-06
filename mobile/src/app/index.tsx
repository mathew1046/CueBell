import { useCallback, useEffect, useRef, useState } from 'react';
import { AccessibilityInfo, AppState, Keyboard, KeyboardAvoidingView, Linking, PermissionsAndroid, Permission,
  Platform, ScrollView, StyleSheet, View } from 'react-native';
import { ActivityIndicator, Appbar, Button, Checkbox, Icon,
  Surface, Text, TextInput, useTheme } from 'react-native-paper';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Listener from '../../modules/queue-listener';
import { api, ensureSession, loadConnection, saveConnection } from '../lib/api';
import { Connection, Intent, NativeSnapshot, QueueAlert, QueueEvent, Rule } from '../lib/types';
import { prepareConsentedSession, requireProcessingConsent } from '../lib/session';

const preferenceLabel = (values: string[]) => values.map(v =>
  ({ visual: 'Visual', vibration: 'Vibration', sound: 'Sound' })[v] ?? v).join(' + ');

export default function Home() {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const [connection, setConnection] = useState<Connection | null>(null);
  const connectionRef = useRef<Connection | null>(null);
  const [consent, setConsent] = useState(false);
  const [request, setRequest] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [proposal, setProposal] = useState<{ id: string; intent: Intent } | null>(null);
  const [clarification, setClarification] = useState('');
  const [showDetails, setShowDetails] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [rule, setRule] = useState<Rule | null>(null);
  const [events, setEvents] = useState<QueueEvent[]>([]);
  const [alerts, setAlerts] = useState<QueueAlert[]>([]);
  const [native, setNative] = useState<NativeSnapshot>(() => JSON.parse(Listener.snapshot()));
  const [booting, setBooting] = useState(true);
  const [permissionError, setPermissionError] = useState(false);
  const analyzing = useRef(false);
  const consentRef = useRef(false);
  const lastSpoken = useRef('');
  const processed = useRef(new Set<string>());
  const revision = useRef(0);
  const suppressMonitor = useRef(false);
  const scroll = useRef<React.ComponentRef<typeof ScrollView>>(null);
  const requestGroupY = useRef(0);
  const confirmationOffset = useRef<number | null>(null);
  const lastHealthAnnouncement = useRef('');

  const addEvent = useCallback((event: QueueEvent) => {
    if (suppressMonitor.current && (event.rule || event.alert || event.type === 'observation' ||
      (event.type === 'transcript' && event.mode !== 'request'))) return;
    const key = event.sequence !== undefined ? `sequence:${event.sequence}` :
      event.segment ? `segment:${event.segment.id}` : undefined;
    if (key) {
      if (processed.current.has(key)) return;
      processed.current.add(key);
      if (processed.current.size > 1000) processed.current.delete(processed.current.values().next().value!);
    }
    if (event.rule || event.alert) revision.current++;
    if (event.rule) setRule(event.rule);
    if (event.type === 'monitor.created') setAlerts([]);
    if (event.alert) {
      const alert = event.alert;
      setAlerts(old => [alert, ...old.filter(a => a.id !== alert.id)].slice(0, 20));
      if (event.type === 'alert' || event.type === 'alert.corrected') {
        AccessibilityInfo.announceForAccessibility(event.type === 'alert.corrected' ?
          'Correction: the previous token call has changed. Check the official display.' :
          `Token ${alert.token} called. ${alert.counter ? `Counter ${alert.counter}.` : 'Counter unknown.'}`);
        scroll.current?.scrollTo({ y: 0, animated: false });
      }
    }
    if (event.type === 'transcript' || event.type === 'observation') {
      setEvents(old => {
        const id = event.segment?.id ?? event.observation?.id;
        if (old.some(e => (e.segment?.id ?? e.observation?.id) === id)) return old;
        return [event, ...old].slice(0, 100);
      });
    }
  }, []);

  const prepareSession = useCallback(async () => {
    const c = await prepareConsentedSession(ensureSession, () => consentRef.current);
    if (connectionRef.current?.token !== c.token) {
      revision.current++;
      Listener.clear(); processed.current.clear(); setEvents([]); setAlerts([]); setRule(null); setProposal(null);
      suppressMonitor.current = c.suppressMonitor ?? false;
    }
    connectionRef.current = c; setConnection(c);
    return c;
  }, []);

  const analyze = useCallback(async (text: string) => {
    if (!text.trim() || analyzing.current || !consentRef.current) return;
    analyzing.current = true; confirmationOffset.current = null;
    setBusy(true); setError(''); setProposal(null); setClarification('');
    try {
      const c = await prepareSession();
      // Request mode closes its stream after the completed utterance. Let teardown finish.
      let result: { status: string; proposal_id?: string; intent: Intent; messages?: string[] } | undefined;
      for (let attempt = 0; attempt < 3; attempt++) {
        try {
          requireProcessingConsent(() => consentRef.current);
          result = await api(c, '/v1/intent', { text, consent_to_text_processing: true });
          break;
        } catch (e) {
          if (attempt < 2 && e instanceof Error && e.message.includes('microphone')) {
            await new Promise(resolve => setTimeout(resolve, 600));
          } else throw e;
        }
      }
      if (result?.status === 'confirm' && result.proposal_id) {
        Keyboard.dismiss();
        setProposal({ id: result.proposal_id, intent: result.intent });
        AccessibilityInfo.announceForAccessibility(`Request ready for review. Token ${result.intent.token}. Nothing has started. Check the details and confirm.`);
      } else setClarification(result?.messages?.join('\n') || 'Please type the exact token and your preferred alert.');
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not interpret the request. Try typing it.'); }
    finally { analyzing.current = false; setBusy(false); }
  }, [prepareSession]);

  const sync = useCallback(() => {
    const snapshot: NativeSnapshot = JSON.parse(Listener.snapshot());
    setNative(snapshot);
    snapshot.events.forEach(addEvent);
    return snapshot;
  }, [addEvent]);

  const refresh = useCallback(async () => {
    sync();
    const c = connectionRef.current;
    if (!c) return;
    const expectedRevision = revision.current;
    try {
      const state = await api<{ rule: Rule | null; history: QueueEvent[]; alerts: QueueAlert[] }>(c, '/v1/state');
      if (revision.current !== expectedRevision || connectionRef.current?.token !== c.token ||
        connectionRef.current?.url !== c.url || suppressMonitor.current) return;
      state.history.forEach(addEvent); setRule(state.rule); setAlerts(state.alerts.slice().reverse());
    } catch (e) {
      if (revision.current === expectedRevision && connectionRef.current?.token === c.token)
        setError(e instanceof Error ? e.message : 'Backend unavailable.');
    }
  }, [addEvent, sync]);

  useEffect(() => {
    const subscription = Listener.addListener('onEvent', ({ json }) => {
      const event: QueueEvent = JSON.parse(json);
      addEvent(event);
      if (event.type === 'status') sync();
      if (event.type === 'transcript' && event.mode === 'request' && event.segment &&
        lastSpoken.current !== event.segment.id) {
        lastSpoken.current = event.segment.id;
        const text = event.segment.text;
        setRequest(text);
        void analyze(text);
      }
    });
    const app = AppState.addEventListener('change', state => { if (state === 'active') void refresh(); });
    void loadConnection().then(c => {
      suppressMonitor.current = c?.suppressMonitor ?? false;
      connectionRef.current = c; setConnection(c);
      void refresh();
    }).catch(() => setError('Could not restore your session. Please try again.'))
      .finally(() => setBooting(false));
    return () => { subscription.remove(); app.remove(); };
  }, [addEvent, analyze, refresh, sync]);

  const run = async (task: () => Promise<void>) => {
    if (busy) return;
    setBusy(true); setError('');
    try { await task(); }
    catch (e) { setError(e instanceof Error ? e.message : 'Something went wrong. Please try again.'); }
    finally { setBusy(false); sync(); }
  };

  const start = useCallback(async (mode: 'request' | 'monitor') => {
    if (!consentRef.current) throw new Error('Please agree to processing before continuing.');
    const c = mode === 'request' ? await prepareSession() : connectionRef.current;
    if (!c || c.expires * 1000 <= Date.now()) throw new Error('Your session has expired. Submit your request again to continue.');
    if (AppState.currentState !== 'active') throw new Error('Open the app to start the microphone.');
    const permissions: Permission[] = [PermissionsAndroid.PERMISSIONS.RECORD_AUDIO];
    if (Number(Platform.Version) >= 33) permissions.push(PermissionsAndroid.PERMISSIONS.POST_NOTIFICATIONS);
    const granted = await PermissionsAndroid.requestMultiple(permissions);
    if (!permissions.every(p => granted[p] === PermissionsAndroid.RESULTS.GRANTED)) {
      setPermissionError(true);
      throw new Error('Microphone and notification permission are needed. You can still type your request.');
    }
    setPermissionError(false);
    requireProcessingConsent(() => consentRef.current);
    try { await Listener.start(c.url, c.token, mode); }
    catch (e) { setPermissionError(true); throw e; }
    // startForegroundService is asynchronous; status events supply the real readiness.
  }, [prepareSession]);

  const control = async (action: 'pause' | 'resume' | 'stop' | 'acknowledge', alertId?: string) => {
    if (!connection) return;
    revision.current++;
    if (action === 'pause' || action === 'stop') await Listener.stop();
    if (action === 'stop') {
      // Local privacy cleanup must not depend on a reachable backend.
      suppressMonitor.current = true;
      setRule(null); setAlerts([]); setEvents([]); Listener.clear(); setProposal(null);
      setRequest(''); setClarification(''); lastSpoken.current = '';
      const next = { ...connection, suppressMonitor: true };
      connectionRef.current = next; setConnection(next);
      try { await saveConnection(next); }
      finally {
        try { await api(connection, '/v1/control', { action, alert_id: null }); }
        catch { throw new Error('Stopped and cleared on this phone. Backend cleanup failed; its session will expire.'); }
      }
      return;
    }
    addEvent(await api<QueueEvent>(connection, '/v1/control', { action, alert_id: alertId ?? null }));
    if (action === 'acknowledge' && alertId) Listener.dismissAlert(alertId);
    if (action === 'resume') await start('monitor');
  };

  const buttonStyle = { minHeight: 48, justifyContent: 'center' as const };
  const activeRule = rule && !['STOPPED', 'EXPIRED'].includes(rule.status);
  const listening = native.running && native.state === 'LISTENING';
  const statusLabel = listening ? (native.mode === 'request' ? 'Speak, then pause' : 'Listening') :
    native.running ? (native.state === 'STARTING' ? 'Starting...' : 'Listening interrupted') : activeRule ? 'Paused' : 'Not listening';
  const statusDetail = native.message !== 'Microphone is off.' && (!listening || /gap|missed|interrupted/i.test(native.message)) ? native.message : '';
  const latestUnclear = events.find(event => event.observation)?.observation?.type === 'UNCERTAIN';
  const muted = { color: theme.colors.onSurfaceVariant };

  useEffect(() => {
    const key = `${native.mode}:${native.state}:${Boolean(activeRule)}`;
    if (lastHealthAnnouncement.current === key) return;
    const initial = lastHealthAnnouncement.current === '';
    lastHealthAnnouncement.current = key;
    if (!initial) AccessibilityInfo.announceForAccessibility(`${statusLabel}. ${native.message}`);
    // Heartbeats and repeated reconnect countdowns do not interrupt TalkBack.
  }, [native.mode, native.state, native.message, activeRule, statusLabel]);

  const screen = <View style={[styles.root, { backgroundColor: theme.colors.background }]}>
    <Appbar.Header style={{ backgroundColor: theme.colors.background }}>
      <Appbar.Content title="CueBell" />
    </Appbar.Header>
    {!!error && <View style={[styles.errorRegion, { backgroundColor: theme.colors.errorContainer }]}>
      <Text variant="bodyLarge" accessibilityRole="alert" accessibilityLiveRegion="assertive"
        style={{ color: theme.colors.onErrorContainer }}>{error}</Text>
      {permissionError && <Button contentStyle={buttonStyle} onPress={() => void Linking.openSettings()}>Open Android permissions</Button>}
      <Button contentStyle={buttonStyle} onPress={() => setError('')} accessibilityLabel="Dismiss error">Dismiss</Button>
    </View>}
    <KeyboardAvoidingView style={styles.root} behavior="padding" keyboardVerticalOffset={0}>
      <ScrollView ref={scroll} keyboardShouldPersistTaps="handled" contentContainerStyle={[
        styles.content, { paddingBottom: Math.max(insets.bottom, 24) + 24 }]}>
        {booting ? <ActivityIndicator accessibilityLabel="Restoring your session" /> : <>
          {alerts.filter(a => a.state !== 'acknowledged' && !a.acknowledged).map(alert => <Surface key={alert.id} elevation={0}
            style={[styles.alert, { backgroundColor: alert.state === 'corrected' ? theme.colors.errorContainer : theme.colors.secondaryContainer }]}>
            <Text variant="headlineSmall" accessibilityRole="header">{alert.state === 'corrected' ? 'Call changed' : 'Your turn'}</Text>
            <Text style={styles.token}>{alert.token}</Text>
            <Text variant="titleLarge">{alert.state === 'corrected' ? 'Previous call corrected or cancelled.' :
              alert.counter ? `Go to counter ${alert.counter}` : 'Counter unclear'}</Text>
            <Text variant="bodyLarge">Check the venue display.</Text>
            <Button mode="contained" contentStyle={buttonStyle} disabled={busy}
              onPress={() => void run(() => control('acknowledge', alert.id))}>I’ve seen this</Button>
          </Surface>)}

          <View style={styles.status} accessible accessibilityLabel={`${statusLabel}. ${statusDetail}`}>
            <Icon source={listening ? 'microphone' : native.running ? 'connection' : 'microphone-off'} size={24}
              color={listening ? theme.colors.primary : theme.colors.onSurfaceVariant} />
            <View style={styles.flex}>
              <Text variant="titleMedium">{statusLabel}</Text>
              {!!statusDetail && <Text variant="bodyMedium" style={muted}>{statusDetail}</Text>}
            </View>
          </View>

          {!native.running && <View>
            <Checkbox.Item label="Allow audio & text processing" status={consent ? 'checked' : 'unchecked'}
              onPress={() => { setConsent(!consent); consentRef.current = !consent; }} position="leading"
              style={styles.checkbox} labelStyle={styles.checkboxLabel} />
            <Text variant="bodyMedium" style={muted}>Audio goes to Gnani. Text goes to OpenAI.</Text>
          </View>}

          {activeRule && <View style={styles.group}>
            <Text variant="titleLarge">Your token</Text>
            <Text style={[styles.token, { color: theme.colors.primary }]}>{rule.token}</Text>
            <Text variant="bodyLarge">{preferenceLabel(rule.alert_preferences)}</Text>
            <View style={styles.row}>
              {native.running ? <Button mode="contained-tonal" icon="pause" contentStyle={buttonStyle} disabled={busy}
                onPress={() => void run(() => control('pause'))}>Pause</Button> :
                <Button mode="contained" icon="microphone" contentStyle={buttonStyle} disabled={busy || !consent}
                  onPress={() => void run(() => control('resume'))}>Start listening</Button>}
              <Button contentStyle={buttonStyle} disabled={busy} onPress={() => void run(() => control('stop'))}>Stop</Button>
            </View>
            {!native.running && <Button contentStyle={buttonStyle} disabled={busy} onPress={() => {
              setProposal(null); setClarification(''); scroll.current?.scrollToEnd({ animated: false });
            }}>Change token</Button>}
          </View>}

          {(!native.running || native.mode === 'request') && <View style={styles.group}
            onLayout={e => {
              requestGroupY.current = e.nativeEvent.layout.y;
              if (proposal && confirmationOffset.current !== null) scroll.current?.scrollTo({
                y: Math.max(0, requestGroupY.current + confirmationOffset.current - 16), animated: false });
            }}>
            <Text variant="headlineSmall" accessibilityRole="header">{activeRule ? 'Change token' : 'Your request'}</Text>
            <TextInput mode="outlined" label="Token and alert" multiline value={request}
              onChangeText={text => { setRequest(text); setProposal(null); setClarification(''); }}
              placeholder="Token 442. Vibrate."
              style={styles.input} maxLength={1500} editable={!busy && !native.running} />
            <View style={styles.row}>
              {native.running ? <Button mode="outlined" icon="stop" contentStyle={buttonStyle}
                onPress={() => void run(async () => { await Listener.stop(); })}>Cancel</Button> :
                <Button mode={request.trim() ? 'outlined' : 'contained'} icon="microphone-outline" contentStyle={styles.speakButton}
                  disabled={!consent || busy} onPress={() => void run(() => start('request'))}>Speak</Button>}
              <Button mode={request.trim() ? 'contained' : 'outlined'} icon="arrow-right" contentStyle={buttonStyle} loading={busy}
                disabled={!consent || busy || native.running || !request.trim()}
                onPress={() => void analyze(request)}>Continue</Button>
            </View>
            {clarification !== '' && <Text variant="bodyLarge" accessibilityLiveRegion="polite" style={{ color: theme.colors.error }}>{clarification}</Text>}
            {proposal && <Surface elevation={0} style={[styles.confirmation, { backgroundColor: theme.colors.surfaceVariant }]}
              onLayout={e => {
                confirmationOffset.current = e.nativeEvent.layout.y;
                scroll.current?.scrollTo({ y: Math.max(0, requestGroupY.current + e.nativeEvent.layout.y - 16), animated: false });
              }}>
              <Text variant="titleLarge">Is this right?</Text>
              <Text style={styles.confirmToken}>{proposal.intent.token}</Text>
              <Text variant="bodyLarge">{preferenceLabel(proposal.intent.alert_preferences)}</Text>
              <Button mode="contained" contentStyle={buttonStyle} disabled={busy || !consent}
                onPress={() => void run(async () => {
                  if (!connection) return;
                  revision.current++;
                  const event = await api<QueueEvent>(connection, '/v1/confirm', { proposal_id: proposal.id });
                  const next = { ...connection, suppressMonitor: false };
                  await saveConnection(next); connectionRef.current = next; setConnection(next);
                  suppressMonitor.current = false; addEvent(event);
                  Listener.clear(); setProposal(null); await start('monitor');
                })}>Start listening</Button>
              <Button contentStyle={buttonStyle} onPress={() => setProposal(null)}>Change</Button>
            </Surface>}
          </View>}

          {(events.length > 0 || activeRule) && <View style={styles.group}>
            <Button icon={showHistory ? 'chevron-up' : 'chevron-down'} contentStyle={buttonStyle}
              accessibilityState={{ expanded: showHistory }} onPress={() => setShowHistory(!showHistory)}>Announcements</Button>
            {latestUnclear && !showHistory && <Text variant="bodyLarge" accessibilityLiveRegion="polite">Unclear announcement. Check the display.</Text>}
            {showHistory && (events.length === 0 ? <Text variant="bodyLarge" style={muted}>No announcements yet.</Text> :
              events.slice(0, 30).map((event, index) => <View key={event.segment?.id ?? event.observation?.id ?? index} style={styles.timelineItem}>
                {event.segment ? <>
                  <Text variant="labelLarge" style={muted}>{event.mode === 'request' ? 'Your spoken request' : 'Announcement transcript'}</Text>
                  <Text variant="bodyLarge" selectable>{event.segment.text}</Text>
                </> : event.observation && <>
                  <Text variant="titleMedium">{event.observation.type === 'UNCERTAIN' ? 'Uncertain · check the display' :
                    `${event.observation.type.toLowerCase()} · ${event.observation.token_normalized ?? 'no token'}`}</Text>
                  <Text variant="bodyMedium" style={muted}>{event.observation.ambiguity_reason ??
                    (event.observation.counter ? `Counter ${event.observation.counter}` : 'Counter not identified')}</Text>
                </>}
              </View>))}
          </View>}
          <Text variant="bodyMedium" style={muted}>Calls may be missed. Check the venue display.</Text>
          <Button contentStyle={buttonStyle} icon={showDetails ? 'chevron-up' : 'information-outline'}
            accessibilityState={{ expanded: showDetails }} onPress={() => setShowDetails(!showDetails)}>About & privacy</Button>
          {showDetails && <View style={styles.group}>
            <Text variant="bodyLarge">For hospital pharmacy tokens: three digits, optionally starting with A or P. Speak Malayalam or English, or type.</Text>
            <Text variant="bodyLarge">Gnani Prisma processes microphone audio. OpenAI processes requests and announcement text. The app and relay save no recordings or transcripts on disk. Provider terms apply.</Text>
            <Text variant="bodyLarge">Android can interrupt listening in the background. Keep the microphone notification visible. This is an aid, not the official queue.</Text>
          </View>}
        </>}
      </ScrollView>
    </KeyboardAvoidingView>
  </View>;
  return screen;
}

const styles = StyleSheet.create({
  root: { flex: 1 }, content: { paddingHorizontal: 24, paddingTop: 16, gap: 24, maxWidth: 640, width: '100%', alignSelf: 'center' },
  group: { gap: 16 }, row: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  status: { flexDirection: 'row', alignItems: 'flex-start', gap: 16 }, flex: { flex: 1, gap: 4 },
  input: { minHeight: 120 }, checkbox: { paddingHorizontal: 0, paddingVertical: 4, minHeight: 48 },
  speakButton: { minHeight: 64 },
  checkboxLabel: { fontSize: 16, textAlign: 'left' },
  confirmation: { padding: 24, borderRadius: 16, gap: 16 },
  alert: { padding: 24, borderRadius: 16, gap: 16 },
  token: { fontSize: 56, fontWeight: '700', fontVariant: ['tabular-nums'] },
  confirmToken: { fontSize: 36, fontWeight: '700', fontVariant: ['tabular-nums'] },
  timelineItem: { gap: 4, paddingVertical: 8 }, errorRegion: { paddingHorizontal: 24, paddingVertical: 12, gap: 8 },
});
