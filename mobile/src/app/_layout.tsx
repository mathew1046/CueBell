import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useColorScheme } from 'react-native';
import { PaperProvider } from 'react-native-paper';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { darkTheme, lightTheme } from '../lib/theme';

export default function Layout() {
  const dark = useColorScheme() === 'dark';
  return <SafeAreaProvider><PaperProvider theme={dark ? darkTheme : lightTheme}>
    <StatusBar style={dark ? 'light' : 'dark'} />
    <Stack screenOptions={{ headerShown: false }} />
  </PaperProvider></SafeAreaProvider>;
}
