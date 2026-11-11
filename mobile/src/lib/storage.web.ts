/** Keep the bearer within this tab's session. Preferences can survive browser restarts. */
function storage(key: string): Storage {
  return key === 'cuebell.connection.v1' ? window.sessionStorage : window.localStorage;
}

const memory = new Map<string, string | null>();

/** Read the current page's value, retaining a fallback when site storage is unavailable. */
export async function getItemAsync(key: string): Promise<string | null> {
  if (typeof window === 'undefined') return null;
  if (memory.has(key)) return memory.get(key) ?? null;
  try {
    const value = storage(key).getItem(key);
    memory.set(key, value);
    return value;
  } catch { return null; }
}

/** Keep writes usable for this page even when persistence is blocked or over quota. */
export async function setItemAsync(key: string, value: string): Promise<void> {
  if (typeof window === 'undefined') return;
  memory.set(key, value);
  try { storage(key).setItem(key, value); } catch { /* The in-memory value remains authoritative. */ }
}

/** A tombstone prevents failed deletion from restoring stale credentials during this page session. */
export async function deleteItemAsync(key: string): Promise<void> {
  if (typeof window === 'undefined') return;
  memory.set(key, null);
  try { storage(key).removeItem(key); } catch { /* Preserve the tombstone when removal is blocked. */ }
}
