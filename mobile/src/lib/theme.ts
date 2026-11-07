import { MD3DarkTheme, MD3LightTheme, useTheme } from 'react-native-paper';

// Larger reading scale: body text never below 16sp, button labels 18sp. System font scaling stays on.
const base = MD3LightTheme.fonts;
const fonts = {
  ...base,
  headlineMedium: { ...base.headlineMedium, fontSize: 30, lineHeight: 38, fontWeight: '700' as const },
  headlineSmall: { ...base.headlineSmall, fontSize: 26, lineHeight: 34, fontWeight: '700' as const },
  titleLarge: { ...base.titleLarge, fontSize: 22, lineHeight: 30, fontWeight: '600' as const },
  titleMedium: { ...base.titleMedium, fontSize: 18, lineHeight: 26, fontWeight: '600' as const },
  bodyLarge: { ...base.bodyLarge, fontSize: 18, lineHeight: 28, letterSpacing: 0.1 },
  bodyMedium: { ...base.bodyMedium, fontSize: 16, lineHeight: 24, letterSpacing: 0.15 },
  labelLarge: { ...base.labelLarge, fontSize: 18, lineHeight: 24, fontWeight: '600' as const, letterSpacing: 0.2 },
};

// Signal colours are identical in light and dark so a call always looks the same.
// Every signal also carries an icon and words; colour is never the only cue.
const call = { background: '#FFD60A', ink: '#111111', edge: '#111111' };
const changed = { background: '#FFDAD6', ink: '#410002', edge: '#B3261E' };

// Soft monochrome: warm paper surfaces, a charcoal hero action, and paired light/dark shadows.
export const lightTheme = { ...MD3LightTheme, roundness: 4, fonts, colors: { ...MD3LightTheme.colors,
  primary: '#2B2B2B', onPrimary: '#FFFFFF', primaryContainer: '#E6E3DF', onPrimaryContainer: '#1C1C1C',
  secondaryContainer: '#E6E3DF', onSecondaryContainer: '#1C1C1C',
  background: '#F2F0ED', surface: '#F6F4F1', surfaceVariant: '#E6E3DF',
  onSurface: '#1C1C1C', onSurfaceVariant: '#4A4744', onBackground: '#1C1C1C',
  outline: '#6B6763', outlineVariant: '#DAD6D1',
  error: '#B3261E', errorContainer: '#FFDAD6', onErrorContainer: '#410002',
}, shadow: {
  soft: '-6px -6px 14px 0px rgba(255,255,255,0.95), 7px 9px 20px 0px rgba(70,58,46,0.14)',
  hero: '0px 20px 36px -6px rgba(0,0,0,0.38)',
  inset: 'inset 3px 3px 6px 0px rgba(70,58,46,0.14), inset -3px -3px 6px 0px rgba(255,255,255,0.9)',
}, signal: {
  call, changed,
  live: { background: '#2B2B2B', ink: '#FFFFFF', edge: '#2B2B2B' },
  warn: { background: '#FFE9A8', ink: '#2B2000', edge: '#7A5C00' },
  idle: { background: '#E6E3DF', ink: '#1C1C1C', edge: '#6B6763' },
} };

export const darkTheme: typeof lightTheme = { ...MD3DarkTheme, roundness: 4, fonts, colors: { ...MD3DarkTheme.colors,
  primary: '#ECEAE6', onPrimary: '#161616', primaryContainer: '#2A2A2A', onPrimaryContainer: '#F2F0ED',
  secondaryContainer: '#2A2A2A', onSecondaryContainer: '#F2F0ED',
  background: '#161616', surface: '#1E1E1E', surfaceVariant: '#2A2A2A',
  onSurface: '#F2F0ED', onSurfaceVariant: '#C4C0BB', onBackground: '#F2F0ED',
  outline: '#8F8A85', outlineVariant: '#343434',
  error: '#FFB4AB', errorContainer: '#5C1410', onErrorContainer: '#FFDAD6',
}, shadow: {
  soft: '-5px -5px 12px 0px rgba(255,255,255,0.045), 8px 10px 22px 0px rgba(0,0,0,0.65)',
  hero: '0px 20px 40px -6px rgba(0,0,0,0.75)',
  inset: 'inset 3px 3px 6px 0px rgba(0,0,0,0.6), inset -3px -3px 6px 0px rgba(255,255,255,0.05)',
}, signal: {
  call, changed,
  live: { background: '#ECEAE6', ink: '#161616', edge: '#ECEAE6' },
  warn: { background: '#4A3A00', ink: '#FFE9A8', edge: '#FFD60A' },
  idle: { background: '#2A2A2A', ink: '#F2F0ED', edge: '#8F8A85' },
} };

export type AppTheme = typeof lightTheme;
export const useAppTheme = () => useTheme<AppTheme>();
