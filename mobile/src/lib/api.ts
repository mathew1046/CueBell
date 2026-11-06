import * as SecureStore from 'expo-secure-store';
import { Connection } from './types';

const KEY = 'queuesaathi.connection.v1';
export const saveConnection = (value: Connection) => SecureStore.setItemAsync(KEY, JSON.stringify(value));
export const removeConnection = () => SecureStore.deleteItemAsync(KEY);
export async function loadConnection(): Promise<Connection | null> {
  const raw = await SecureStore.getItemAsync(KEY);
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as Connection;
    return value.expires * 1000 > Date.now() ? value : null;
  } catch { return null; }
}
export function secureUrl(raw: string): string {
  const url = new URL(raw.trim());
  if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash ||
    (url.pathname !== '/' && url.pathname !== '')) {
    throw new Error('Enter an HTTPS origin, for example https://queue.example.org (no path).');
  }
  return url.origin;
}
export async function api<T>(connection: Connection | string, path: string, body?: object,
  method = body ? 'POST' : 'GET'): Promise<T> {
  const url = typeof connection === 'string' ? connection : connection.url;
  const response = await fetch(url + path, {
    method, headers: { 'Content-Type': 'application/json',
      ...(typeof connection === 'string' ? {} : { Authorization: `Bearer ${connection.token}` }) },
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(20000),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail :
    `Backend request failed (${response.status}). Check the connection settings.`);
  return result as T;
}
