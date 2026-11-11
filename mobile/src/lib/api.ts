import * as SecureStore from './storage';
import { Connection } from './types';
import { createSessionManager, serviceOrigin } from './session';

// Public routing configuration, supplied by the operator before building the APK.
// This is not an API key. End users never enter or change it.
const SERVICE_URL = process.env.EXPO_PUBLIC_API_URL ?? '';
export class SessionExpiredError extends Error {}

const KEY = 'cuebell.connection.v1';
export const saveConnection = (value: Connection) => SecureStore.setItemAsync(KEY, JSON.stringify(value));
export const removeConnection = () => SecureStore.deleteItemAsync(KEY);
export async function loadConnection(): Promise<Connection | null> {
  const raw = await SecureStore.getItemAsync(KEY);
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as Connection;
    return value.url === serviceOrigin(SERVICE_URL) && typeof value.token === 'string' &&
      value.token.length > 0 && Number.isFinite(value.expires) && value.expires * 1000 > Date.now() ? value : null;
  } catch { return null; }
}
export const ensureSession = createSessionManager({
  origin: SERVICE_URL, load: loadConnection, save: saveConnection,
  create: origin => api(origin, '/v1/sessions', {}),
  validate: async connection => {
    try { await api(connection, '/v1/state'); return true; }
    catch (error) { if (error instanceof SessionExpiredError) return false; throw error; }
  },
});
export async function api<T>(connection: Connection | string, path: string, body?: object,
  method = body ? 'POST' : 'GET'): Promise<T> {
  const url = typeof connection === 'string' ? connection : connection.url;
  const response = await fetch(url + path, {
    method, headers: { 'Content-Type': 'application/json',
      ...(typeof connection === 'string' ? {} : { Authorization: `Bearer ${connection.token}` }) },
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(20000),
  }).catch(() => { throw new Error('Could not reach CueBell. Check your internet connection and try again.'); });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof result.detail === 'string' ? result.detail : '';
    if (response.status === 401) {
      if (typeof connection === 'string') throw new Error('CueBell is temporarily unavailable. Please try again later.');
      if (typeof connection !== 'string' && (await loadConnection())?.token === connection.token) {
        await removeConnection();
      }
      throw new SessionExpiredError('Your session has expired. Submit your request again to continue.');
    }
    if (response.status === 429) throw new Error('CueBell is busy right now. Please try again shortly.');
    if (response.status === 403 || response.status >= 500 || /backend|configure|API.key|access.code/i.test(detail)) {
      throw new Error('CueBell is temporarily unavailable. Please try again later.');
    }
    throw new Error(detail || 'Could not complete the request. Please try again.');
  }
  return result as T;
}
