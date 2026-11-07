import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { PaperProvider } from 'react-native-paper';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { AlertTakeover } from '../components/ui';
import { useReduceMotion } from '../lib/a11y';
import { CueBellProvider, useCueBell } from '../lib/cuebell';
import { darkTheme, lightTheme } from '../lib/theme';
import { ThemeModeProvider, useThemeMode } from '../lib/themeMode';

function GlobalAlerts() {
  const app = useCueBell();
  const reduceMotion = useReduceMotion();
  const alert = app.takeover;
  return <AlertTakeover alert={alert} more={app.outstanding.length - 1} visible={!!alert} busy={app.busy} reduceMotion={reduceMotion}
    onSeen={() => alert && app.acknowledge(alert.id)} onLater={() => alert && app.deferAlert(alert.id)} />;
}

function Themed() {
  const { dark } = useThemeMode();
  const theme = dark ? darkTheme : lightTheme;
  return <PaperProvider theme={theme}>
    <StatusBar style={dark ? 'light' : 'dark'} />
    <CueBellProvider>
      <Stack screenOptions={{ headerShown: false, animation: 'none', contentStyle: { backgroundColor: theme.colors.background } }} />
      <GlobalAlerts />
    </CueBellProvider>
  </PaperProvider>;
}

export default function Layout() {
  return <SafeAreaProvider><ThemeModeProvider><Themed /></ThemeModeProvider></SafeAreaProvider>;
}
