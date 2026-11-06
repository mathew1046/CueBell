import { MD3DarkTheme, MD3LightTheme } from 'react-native-paper';
export const lightTheme = { ...MD3LightTheme, colors: { ...MD3LightTheme.colors,
  primary: '#075E54', onPrimary: '#FFFFFF', background: '#F1F8F6', surface: '#FFFFFF',
  surfaceVariant: '#DFECE6', onSurfaceVariant: '#3E4944', secondaryContainer: '#C4ECDD',
  onSecondaryContainer: '#002C23', onSurface: '#102F29', error: '#BA1A1A', outline: '#64776E',
} };
export const darkTheme = { ...MD3DarkTheme, colors: { ...MD3DarkTheme.colors,
  primary: '#85D5BE', onPrimary: '#00382E', background: '#101E1A', surface: '#172B24',
  surfaceVariant: '#293D34', onSurfaceVariant: '#C1CEC6', secondaryContainer: '#244C40',
  onSecondaryContainer: '#C4ECDD', onSurface: '#E0F2E9', error: '#FFB4AB', outline: '#94A79D',
} };
