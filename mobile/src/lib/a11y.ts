import { useEffect, useState } from 'react';
import { AccessibilityInfo, Vibration } from 'react-native';

/** Screen readers read "442" as a number; tokens must be heard character by character. */
export const spell = (token: string | null | undefined) => (token ?? '').split('').join(' ');

const labels: Record<string, string> = { visual: 'On screen', vibration: 'Vibrate', sound: 'Alarm sound' };
export const preferenceLabel = (values: string[]) => values.map(v => labels[v] ?? v).join(', ');

/** Distinct, short haptic patterns so deaf-blind users can feel state changes. */
export const haptic = {
  tap: () => Vibration.vibrate(20),
  listening: () => Vibration.vibrate([0, 60, 90, 60]),
  stopped: () => Vibration.vibrate(220),
};

export function useReduceMotion() {
  const [reduce, setReduce] = useState(true);
  useEffect(() => {
    void AccessibilityInfo.isReduceMotionEnabled().then(setReduce);
    const sub = AccessibilityInfo.addEventListener('reduceMotionChanged', setReduce);
    return () => sub.remove();
  }, []);
  return reduce;
}
