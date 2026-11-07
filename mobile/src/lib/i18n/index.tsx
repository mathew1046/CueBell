import * as SecureStore from 'expo-secure-store';
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, View } from 'react-native';
import Listener from '../../../modules/queue-listener';
import catalogs from './catalogs.json';
import { isLanguage, languages, type Language } from './languages';
import { translate, type Parameters } from './translate';

const KEY = 'cuebell.language.v1';
const Context = createContext<{
  language: Language; setLanguage: (language: Language) => void;
  t: (message: string, parameters?: Parameters) => string; storageError: boolean;
} | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, updateLanguage] = useState<Language>('en');
  const [ready, setReady] = useState(false);
  const [storageError, setStorageError] = useState(false);
  const writes = useRef(Promise.resolve());
  useEffect(() => {
    let mounted = true;
    void SecureStore.getItemAsync(KEY).then(value => {
      if (mounted && isLanguage(value)) updateLanguage(value);
    }).catch(() => { if (mounted) setStorageError(true); })
      .finally(() => { if (mounted) setReady(true); });
    return () => { mounted = false; };
  }, []);
  useEffect(() => {
    if (ready) Listener.setLanguage(language, JSON.stringify((catalogs as Record<string, unknown>)[language] ?? {}));
  }, [language, ready]);
  const setLanguage = useCallback((next: Language) => {
    if (!isLanguage(next)) return;
    updateLanguage(next);
    // Serialize writes: rapid selections must not restore an older choice at next launch.
    writes.current = writes.current.then(() => SecureStore.setItemAsync(KEY, next))
      .then(() => setStorageError(false), () => setStorageError(true));
  }, []);
  const t = useCallback((message: string, parameters?: Parameters) => translate(language, message, parameters), [language]);
  const value = useMemo(() => ({ language, setLanguage, t, storageError }), [language, setLanguage, t, storageError]);
  if (!ready) return <View style={{ flex: 1, justifyContent: 'center' }}><ActivityIndicator accessibilityLabel="CueBell" /></View>;
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useLanguage() {
  const value = useContext(Context);
  if (!value) throw new Error('LanguageProvider is missing.');
  return value;
}
export { languages };
