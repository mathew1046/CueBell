import * as SecureStore from './storage';
import { createContext, ReactNode, useContext, useEffect, useState } from 'react';
import { useColorScheme } from 'react-native';

export type ThemeMode = 'system' | 'light' | 'dark';
const KEY = 'cuebell.theme.v1';
const Context = createContext<{ mode: ThemeMode; dark: boolean; setMode: (mode: ThemeMode) => void }>({
  mode: 'system', dark: false, setMode: () => {},
});

export function ThemeModeProvider({ children }: { children: ReactNode }) {
  const system = useColorScheme();
  const [mode, setModeState] = useState<ThemeMode>('system');
  useEffect(() => {
    void SecureStore.getItemAsync(KEY).then(value => {
      if (value === 'light' || value === 'dark' || value === 'system') setModeState(value);
    }).catch(() => {});
  }, []);
  const setMode = (next: ThemeMode) => { setModeState(next); void SecureStore.setItemAsync(KEY, next).catch(() => {}); };
  const dark = mode === 'system' ? system === 'dark' : mode === 'dark';
  return <Context.Provider value={{ mode, dark, setMode }}>{children}</Context.Provider>;
}

export const useThemeMode = () => useContext(Context);
