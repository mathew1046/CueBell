/** Keep the bearer within this tab's session. Preferences can survive browser restarts. */
function storage(key: string): Storage {
  return key === 'cuebell.connection.v1' ? window.sessionStorage : window.localStorage;
}

export async function getItemAsync(key: string): Promise<string | null> {
  if (typeof window === 'undefined') return null;
  return storage(key).getItem(key);
}

export async function setItemAsync(key: string, value: string): Promise<void> {
  storage(key).setItem(key, value);
}

export async function deleteItemAsync(key: string): Promise<void> {
  storage(key).removeItem(key);
}
