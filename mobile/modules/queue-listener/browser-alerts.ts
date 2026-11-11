import type { QueueEvent } from '../../src/lib/types';

let context: AudioContext | null = null;
let language = 'en';
let catalog: Record<string, string> = {};
const notifications = new Map<string, Notification>();
const pendingNotifications = new Map<string, symbol>();
const announced = new Set<string>();
const tones = new Set<OscillatorNode>();
let spokenPreference: boolean | null = null;

export function audioContext(): AudioContext {
  context ??= new AudioContext();
  return context;
}

/** Resume during a user gesture so subsequent requested alarms can play. */
export function primeAudio(): void {
  if (typeof window === 'undefined' || !window.AudioContext) return;
  try { void audioContext().resume().catch(() => {}); } catch { /* Capture reports unavailable audio when started. */ }
}

function text(message: string, parameters: Record<string, string> = {}) {
  return (catalog[message] || message).replace(/\{(\w+)\}/g, (match, key: string) => parameters[key] ?? match);
}

export function setLanguage(next: string, translations: string): void {
  language = next;
  try { catalog = JSON.parse(translations); } catch { catalog = {}; }
  if (typeof document !== 'undefined') {
    document.documentElement.lang = language;
    document.documentElement.dir = ['ur', 'sd'].includes(language) ? 'rtl' : 'ltr';
  }
}

export function spokenAlertsEnabled(): boolean {
  if (spokenPreference !== null) return spokenPreference;
  try { spokenPreference = localStorage.getItem('cuebell.spoken.v1') === 'true'; } catch { spokenPreference = false; }
  return spokenPreference;
}

export function setSpokenAlertsEnabled(enabled: boolean): void {
  spokenPreference = enabled;
  try { localStorage.setItem('cuebell.spoken.v1', String(enabled)); } catch { /* Usable for this session via the control. */ }
}

export function silenceAlerts(): void {
  for (const tone of tones) { try { tone.stop(); } catch {} }
  tones.clear();
  navigator.vibrate?.(0);
  window.speechSynthesis?.cancel();
}

export function dismissAlert(id: string): void {
  pendingNotifications.delete(id);
  notifications.get(id)?.close();
  notifications.delete(id);
  if ('serviceWorker' in navigator) {
    void navigator.serviceWorker.getRegistration().then(async registration => {
      for (const notification of await registration?.getNotifications({ tag: `cuebell:${id}` }) ?? []) notification.close();
    }).catch(() => {});
  }
  silenceAlerts();
}

export function clearAlerts(): void {
  for (const notification of notifications.values()) notification.close();
  notifications.clear();
  pendingNotifications.clear();
  announced.clear();
  silenceAlerts();
  if ('serviceWorker' in navigator) {
    void navigator.serviceWorker.getRegistration().then(async registration => {
      for (const notification of await registration?.getNotifications() ?? []) notification.close();
    }).catch(() => {});
  }
}

/** Deliver each grounded alert once, respecting independent sound and vibration choices. */
export function showAlert(event: QueueEvent): void {
  const alert = event.alert;
  if (!alert || !['alert', 'alert.corrected'].includes(event.type)) return;
  const key = event.sequence === undefined
    ? JSON.stringify([event.type, alert.id, alert.state, alert.summary, alert.counter, alert.location])
    : `sequence:${event.sequence}`;
  if (announced.has(key)) return;
  announced.add(key);
  if (announced.size > 100) announced.delete(announced.values().next().value!);
  const corrected = event.type === 'alert.corrected';
  const title = text(corrected ? 'Correction · check the announcement' : alert.summary ? 'Event detected' : "It's your turn!");
  const body = corrected ? text('The previous alert was corrected or cancelled. Check the official source.') :
    alert.summary || text('Token {token}. {counter}', { token: alert.token ?? '',
      counter: alert.counter ? text('Go to counter {counter}.', { counter: alert.counter }) : text('Counter unknown — check the display.') });

  if (alert.alert_preferences.includes('vibration')) navigator.vibrate?.([400, 200, 400, 200, 700]);
  if (alert.alert_preferences.includes('sound')) {
    const audio = audioContext();
    if (audio.state === 'running') {
      for (let pulse = 0; pulse < 3; pulse++) {
        const tone = audio.createOscillator();
        const gain = audio.createGain();
        const start = audio.currentTime + pulse * 0.8;
        tone.frequency.value = corrected ? 520 : 740;
        gain.gain.setValueAtTime(0, start);
        gain.gain.linearRampToValueAtTime(0.25, start + 0.03);
        gain.gain.setValueAtTime(0.25, start + 0.45);
        gain.gain.linearRampToValueAtTime(0, start + 0.5);
        tone.connect(gain).connect(audio.destination);
        tone.onended = () => { tone.disconnect(); gain.disconnect(); tones.delete(tone); };
        tones.add(tone);
        tone.start(start);
        tone.stop(start + 0.51);
      }
    }
    if (spokenAlertsEnabled() && window.speechSynthesis) {
      const utterance = new SpeechSynthesisUtterance(`${title}. ${body}`);
      utterance.lang = language;
      // Only use locally installed voices so private announcement text stays on this device.
      const voice = speechSynthesis.getVoices().find(voice => voice.localService && voice.lang.split('-')[0] === language);
      if (voice) { utterance.voice = voice; speechSynthesis.speak(utterance); }
    }
  }
  if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
    const delivery = Symbol();
    pendingNotifications.set(alert.id, delivery);
    const options = { body, tag: `cuebell:${alert.id}`, icon: '/icons/icon-192.png', silent: true };
    void (async () => {
      const registration = await navigator.serviceWorker?.getRegistration();
      if (pendingNotifications.get(alert.id) !== delivery) return;
      if (registration) {
        await registration.showNotification(title, { ...options, data: { url: '/' } });
        if (!pendingNotifications.has(alert.id)) {
          for (const notification of await registration.getNotifications({ tag: options.tag })) notification.close();
        }
      }
      else {
        notifications.get(alert.id)?.close();
        const notification = new Notification(title, options);
        notification.onclick = () => { window.focus(); notification.close(); };
        notifications.set(alert.id, notification);
      }
    })().catch(() => { /* The in-app alert remains available when OS notifications are blocked. */ });
  }
}
