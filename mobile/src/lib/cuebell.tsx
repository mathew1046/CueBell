import { createContext, ReactNode, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { AppState, Keyboard } from 'react-native';
import Listener from '../../modules/queue-listener';
import type { Tone } from '../components/ui';
import { haptic, spell } from './a11y';
import { api, ensureSession, loadConnection, removeConnection, saveConnection } from './api';
import { CaptureOperation, listeningPhase } from './listening';
import { prepareConsentedSession, requireProcessingConsent } from './session';
import { stopListening } from './stop-listening';
import { startListeningIfCurrent } from './start-listening';
import { prepareCaptureGesture, releaseCapturePermission, requestCapturePermissions } from './capture-permissions';
import { announce } from './announce';
import { Connection, Intent, NativeSnapshot, QueueAlert, QueueEvent, Rule } from './types';
import { useLanguage } from './i18n';
import { translateServiceMessage } from './i18n/translate';

function useCueBellState() {
  const { t, language } = useLanguage();
  const translator = useRef(t);
  useEffect(() => { translator.current = t; }, [t]);
  const [connection, setConnection] = useState<Connection | null>(null);
  const connectionRef = useRef<Connection | null>(null);
  const [consent, setConsent] = useState(false);
  const [request, setRequest] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [proposal, setProposal] = useState<{ id: string; intent: Intent } | null>(null);
  const [clarification, setClarification] = useState('');
  const [rule, setRule] = useState<Rule | null>(null);
  const [events, setEvents] = useState<QueueEvent[]>([]);
  const [alerts, setAlerts] = useState<QueueAlert[]>([]);
  const [native, setNative] = useState<NativeSnapshot>(() => JSON.parse(Listener.snapshot()));
  const [booting, setBooting] = useState(true);
  const [permissionError, setPermissionError] = useState(false);
  const [captureError, setCaptureError] = useState(false);
  const [operation, setOperation] = useState<CaptureOperation | null>(null);
  const [laterAlerts, setLaterAlerts] = useState<string[]>([]);
  const analyzing = useRef(false);
  const operating = useRef(false);
  const consentRef = useRef(false);
  const lastSpoken = useRef('');
  const processed = useRef(new Set<string>());
  const revision = useRef(0);
  const suppressMonitor = useRef(false);
  const lastHealthAnnouncement = useRef('');
  const lastListening = useRef<boolean | null>(null);
  const setupAttempt = useRef(0);

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
        announce(event.type === 'alert.corrected' ?
          translator.current('The previous alert was corrected or cancelled. Check the official source.') :
          alert.summary ? translator.current('Event detected. {summary}', { summary: alert.summary }) :
          translator.current('Your turn. Token {token} called. {counter}', { token: spell(alert.token ?? ''), counter: alert.counter ? translator.current('Counter {counter}.', { counter: alert.counter }) : translator.current('Counter unknown.') }));
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

  const start = useCallback(async (
    mode: 'request' | 'monitor',
    activate?: (connection: Connection) => Promise<void>,
    current: () => boolean = () => true,
  ) => {
    const attempt = setupAttempt.current;
    const allowed = () => current() && setupAttempt.current === attempt;
    setCaptureError(false);
    setPermissionError(false);
    try {
      requireProcessingConsent(() => consentRef.current);
      const snapshot: NativeSnapshot = JSON.parse(Listener.snapshot());
      const handoff = mode === 'monitor' && snapshot.running && snapshot.mode === 'request' && snapshot.state === 'PROCESSING';
      if (!handoff && AppState.currentState !== 'active') throw new Error('Open the app to start the microphone.');
      await requestCapturePermissions(() => setOperation({ mode, phase: 'REQUESTING_PERMISSION' }));
      requireProcessingConsent(() => consentRef.current);
      if (!allowed()) return;
      setOperation({ mode, phase: 'CONNECTING' });
      const c = mode === 'request' ? await prepareSession() : connectionRef.current;
      if (!c || c.expires * 1000 <= Date.now()) {
        throw new Error('Your session has expired. Submit your request again to continue.');
      }
      try {
        await startListeningIfCurrent(() => {
          requireProcessingConsent(() => consentRef.current);
          return allowed();
        }, async () => { await activate?.(c); }, async () => { await Listener.start(c.url, c.token, mode); });
      } catch (error) {
        if (error instanceof Error && /permission|notification/i.test(error.message)) setPermissionError(true);
        throw error;
      }
    } catch (error) {
      setCaptureError(true);
      if (error instanceof Error && /permission|notification|microphone access/i.test(error.message)) setPermissionError(true);
      throw error;
    } finally {
      releaseCapturePermission();
    }
  }, [prepareSession]);

  const activateProposal = useCallback(async (id: string, current: () => boolean = () => true) => {
    await start('monitor', async c => {
      revision.current++;
      const event = await api<QueueEvent>(c, '/v1/confirm', { proposal_id: id });
      if (!current()) return;
      const next = { ...c, suppressMonitor: false };
      await saveConnection(next);
      if (!current()) return;
      connectionRef.current = next; setConnection(next);
      suppressMonitor.current = false;
      Listener.clear();
      setEvents(old => old.filter(item => item.mode === 'request'));
      addEvent(event);
      setProposal(null);
    }, current);
  }, [addEvent, start]);

  const analyze = useCallback(async (text: string) => {
    if (!text.trim() || analyzing.current || !consentRef.current) return;
    analyzing.current = true;
    const attempt = ++setupAttempt.current;
    const current = () => setupAttempt.current === attempt && consentRef.current;
    setBusy(true); setError(''); setProposal(null); setClarification('');
    setOperation({ mode: 'request', phase: 'PROCESSING' });
    try {
      const c = await prepareSession();
      if (!current()) return;
      // Request mode closes its stream after the completed utterance. Let teardown finish.
      let result: { status: string; proposal_id?: string; intent: Intent; messages?: string[] } | undefined;
      for (let attempt = 0; attempt < 3; attempt++) {
        try {
          requireProcessingConsent(() => consentRef.current);
          if (!current()) return;
          result = await api(c, '/v1/intent', { text, consent_to_text_processing: true });
          break;
        } catch (e) {
          if (attempt < 2 && e instanceof Error && e.message.includes('microphone')) {
            await new Promise(resolve => setTimeout(resolve, 600));
          } else throw e;
        }
      }
      if (!current()) return;
      if (result?.status === 'confirm' && result.proposal_id) {
        Keyboard.dismiss();
        setProposal({ id: result.proposal_id, intent: result.intent });
        await activateProposal(result.proposal_id, current);
      } else setClarification(result?.messages?.join('\n') || 'Describe what to listen for and when to alert you.');
    } catch (e) { if (current()) setError(e instanceof Error ? e.message : 'Could not interpret the request. Try typing it.'); }
    finally {
      // Unsupported/unclear requests must not leave the foreground microphone service waiting.
      const snapshot: NativeSnapshot = JSON.parse(Listener.snapshot());
      if (snapshot.mode === 'request' && snapshot.state === 'PROCESSING') {
        try { await Listener.stop(); }
        catch { setError('Could not turn off the microphone. Use Stop microphone in the notification.'); }
      }
      analyzing.current = false;
      setOperation(null); setBusy(false);
    }
  }, [activateProposal, prepareSession]);

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
      if (event.type === 'status') {
        if (['STOPPING', 'STOPPED', 'ERROR'].includes(event.state ?? '')) setupAttempt.current++;
        sync();
      }
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
    if (operating.current || analyzing.current) return;
    operating.current = true;
    setBusy(true); setError('');
    try { await task(); }
    catch (e) { setError(e instanceof Error ? e.message : 'Something went wrong. Please try again.'); }
    finally {
      sync();
      setOperation(null);
      setBusy(false);
      operating.current = false;
    }
  };

  const control = async (action: 'pause' | 'resume' | 'stop' | 'acknowledge', alertId?: string) => {
    revision.current++;
    if (action === 'pause' || action === 'stop') {
      setOperation({ mode: 'monitor', phase: 'STOPPING' });
      await stopListening(action, connection, {
        stopCapture: async () => { await Listener.stop(); setCaptureError(false); },
        clearLocal: () => {
          // Local privacy cleanup must not depend on a restored or reachable backend.
          suppressMonitor.current = true;
          setRule(null); setAlerts([]); setEvents([]); Listener.clear(); setProposal(null);
          setRequest(''); setClarification(''); lastSpoken.current = '';
        },
        setConnection: next => { connectionRef.current = next; setConnection(next); },
        save: saveConnection, remove: removeConnection,
        remote: (c, command) => api<QueueEvent>(c, '/v1/control', { action: command, alert_id: null })
          .then(event => { if (command === 'pause') addEvent(event); }),
      });
      return;
    }
    if (!connection) return;
    if (action === 'resume') {
      await start('monitor', async c => addEvent(await api<QueueEvent>(c, '/v1/control', { action })));
      return;
    }
    addEvent(await api<QueueEvent>(connection, '/v1/control', { action, alert_id: alertId ?? null }));
    if (action === 'acknowledge' && alertId) Listener.dismissAlert(alertId);
  };

  const confirm = () => run(async () => {
    if (!proposal) return;
    await activateProposal(proposal.id);
  });

  const activeRule = rule && !['STOPPED', 'EXPIRED'].includes(rule.status) ? rule : null;
  const phase = listeningPhase(native, operation, captureError);
  const captureMode = operation?.mode ?? native.mode;
  const listening = phase === 'LISTENING';
  const capturing = native.running && native.mode === 'request' && native.state !== 'PROCESSING';
  const statusLabel = t({
    IDLE: 'Not listening',
    REQUESTING_PERMISSION: 'Waiting for permission',
    CONNECTING: 'Connecting...',
    LISTENING: captureMode === 'request' ? 'Speak now' : 'Listening',
    PROCESSING: 'Creating event...',
    RECONNECTING: 'Reconnecting...',
    STOPPING: 'Stopping...',
    ERROR: 'Listening unavailable',
  }[phase]);
  const statusDetail = (phase === 'RECONNECTING' || (phase === 'ERROR' && native.state === 'ERROR') ||
    (listening && /gap|missed|interrupted/i.test(native.message))) ? translateServiceMessage(language, native.message, 'Listening interrupted. Check the display and try again.') : '';
  const tone: Tone = listening ? 'live' : phase === 'RECONNECTING' || phase === 'ERROR' ? 'warn' : 'idle';
  const statusIcon = {
    IDLE: 'microphone-off', REQUESTING_PERMISSION: 'shield-lock-outline', CONNECTING: 'progress-clock',
    LISTENING: captureMode === 'request' ? 'account-voice' : 'microphone',
    PROCESSING: 'progress-clock', RECONNECTING: 'access-point-network-off', STOPPING: 'progress-clock', ERROR: 'alert-circle-outline',
  }[phase];
  const latestUnclear = events.find(event => event.observation)?.observation?.type === 'UNCERTAIN';
  const outstanding = alerts.filter(a => a.state !== 'acknowledged' && !a.acknowledged);
  const takeover = outstanding.find(a => !laterAlerts.includes(a.id));

  useEffect(() => {
    const key = `${captureMode}:${phase}`;
    if (lastHealthAnnouncement.current === key) return;
    const initial = lastHealthAnnouncement.current === '';
    lastHealthAnnouncement.current = key;
    if (!initial) announce(statusDetail ? `${statusLabel}. ${statusDetail}` : statusLabel);
    // Heartbeats and repeated reconnect countdowns do not interrupt TalkBack.
  }, [captureMode, phase, statusDetail, statusLabel]);

  useEffect(() => {
    if (lastListening.current !== null && lastListening.current !== listening) (listening ? haptic.listening : haptic.stopped)();
    lastListening.current = listening;
  }, [listening]);

  return {
    consent, toggleConsent: () => { consentRef.current = !consent; setConsent(!consent); haptic.tap(); },
    request, editRequest: (text: string) => { setRequest(text); setProposal(null); setClarification(''); },
    busy, error: translateServiceMessage(language, error, 'Something went wrong. Please try again.'), clearError: () => setError(''), permissionError, booting,
    // Model clarifications are user-facing content in the request's language. Do not
    // hide an unsupported-capability explanation behind a generic setup prompt.
    proposal, clearProposal: () => setProposal(null), clarification: translateServiceMessage(language, clarification, clarification),
    activeRule, events, outstanding, takeover, latestUnclear,
    native, phase, captureMode, listening, capturing, statusLabel, statusDetail, statusIcon, tone,
    analyze: (text: string) => { prepareCaptureGesture(); void analyze(text); },
    speak: () => { prepareCaptureGesture(); void run(async () => { haptic.tap(); await start('request'); }); },
    cancelCapture: () => void (async () => {
      setupAttempt.current++;
      setOperation({ mode: 'request', phase: 'STOPPING' });
      try { await Listener.stop(); }
      catch (e) { setError(e instanceof Error ? e.message : 'Something went wrong. Please try again.'); }
      finally { sync(); setOperation(null); }
    })(),
    confirm: () => { prepareCaptureGesture(); void confirm(); },
    pause: () => void run(() => control('pause')),
    resume: () => { prepareCaptureGesture(); void run(() => control('resume')); },
    stop: () => void run(() => control('stop')),
    acknowledge: (id: string) => void run(async () => { haptic.tap(); await control('acknowledge', id); }),
    deferAlert: (id: string) => setLaterAlerts(old => [...old, id]),
    showAlert: (id: string) => setLaterAlerts(old => old.filter(value => value !== id)),
  };
}

type CueBell = ReturnType<typeof useCueBellState>;
const Context = createContext<CueBell | null>(null);

export function CueBellProvider({ children }: { children: ReactNode }) {
  return <Context.Provider value={useCueBellState()}>{children}</Context.Provider>;
}

export function useCueBell() {
  const value = useContext(Context);
  if (!value) throw new Error('CueBellProvider is missing.');
  return value;
}
