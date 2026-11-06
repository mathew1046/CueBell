import type { Connection } from './types';

export function serviceOrigin(raw: string): string {
  try {
    const url = new URL(raw.trim());
    if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash ||
      (url.pathname !== '/' && url.pathname !== '')) throw new Error();
    return url.origin;
  } catch {
    throw new Error('CueBell is temporarily unavailable. Please try again later.');
  }
}

type SessionOptions = {
  origin: string;
  load: () => Promise<Connection | null>;
  save: (value: Connection) => Promise<void>;
  create: (origin: string) => Promise<{ token: string; expires_at: number }>;
  validate?: (value: Connection) => Promise<boolean>;
  now?: () => number;
};

// One session admission for concurrent taps. Never ship a pairing secret in the app.
export function createSessionManager(options: SessionOptions) {
  let pending: Promise<Connection> | null = null;
  return () => {
    if (pending) return pending;
    pending = (async () => {
      const origin = serviceOrigin(options.origin);
      const now = options.now?.() ?? Date.now();
      const stored = await options.load();
      if (stored?.url === origin && typeof stored.token === 'string' && stored.token.length > 0 &&
        Number.isFinite(stored.expires) && stored.expires * 1000 > now + 30000 &&
        (!options.validate || await options.validate(stored))) return stored;
      const result = await options.create(origin);
      if (!result.token || !Number.isFinite(result.expires_at) || result.expires_at * 1000 <= now) {
        throw new Error('Could not start a session. Please try again.');
      }
      const connection: Connection = { url: origin, token: result.token, expires: result.expires_at };
      await options.save(connection);
      return connection;
    })().finally(() => { pending = null; });
    return pending;
  };
}

export function requireProcessingConsent(consented: () => boolean) {
  if (!consented()) throw new Error('Processing was not allowed. Please agree before continuing.');
}

export async function prepareConsentedSession(ensure: () => Promise<Connection>, consented: () => boolean) {
  requireProcessingConsent(consented);
  const value = await ensure();
  requireProcessingConsent(consented);
  return value;
}
