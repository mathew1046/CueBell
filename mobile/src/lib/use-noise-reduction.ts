import * as SecureStore from './storage';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Platform } from 'react-native';
import type { NoiseReductionMode } from '../../modules/queue-listener';
import { readNoiseReductionMode } from './noise-reduction';

const KEY = 'cuebell.noise-reduction.v1';

export function useNoiseReductionPreference() {
  const [mode, updateMode] = useState<NoiseReductionMode>('off');
  const [ready, setReady] = useState(Platform.OS !== 'android');
  const [storageError, setStorageError] = useState('');
  const selected = useRef<NoiseReductionMode>('off');
  const restored = useRef(false);
  const loading = useRef(Promise.resolve());
  const writes = useRef(Promise.resolve());

  useEffect(() => {
    if (Platform.OS !== 'android') return;
    let mounted = true;
    loading.current = SecureStore.getItemAsync(KEY).then(value => {
      if (!mounted) return;
      selected.current = readNoiseReductionMode(value);
      updateMode(selected.current);
    }).catch(() => {
      if (mounted) setStorageError('Noise reduction could not be restored. Off is selected.');
    }).finally(() => {
      if (!mounted) return;
      restored.current = true;
      setReady(true);
    });
    return () => { mounted = false; };
  }, []);

  const setMode = useCallback((next: NoiseReductionMode) => {
    if (Platform.OS !== 'android' || !restored.current) return;
    selected.current = readNoiseReductionMode(next);
    updateMode(selected.current);
    // Rapid changes must persist in order, including an explicit return to Off.
    writes.current = writes.current.then(() => SecureStore.setItemAsync(KEY, next))
      .then(() => setStorageError(''), () => setStorageError('Noise reduction could not be saved. Select it again to retry.'));
  }, []);

  const getMode = useCallback(async () => {
    await loading.current;
    return selected.current;
  }, []);

  return { mode, ready, storageError, getMode, setMode };
}
