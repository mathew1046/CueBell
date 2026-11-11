import { useEffect, useState } from 'react';
import { View } from 'react-native';
import { Button, Text } from 'react-native-paper';
import { useLanguage } from '../lib/i18n';
import { useAppTheme } from '../lib/theme';
import { SoftCard } from './ui';

type InstallEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> };

/** Expose browser capabilities next to the listening workflow before users depend on alerts. */
export function WebAppSupport() {
  const { t } = useLanguage();
  const theme = useAppTheme();
  const [install, setInstall] = useState<InstallEvent | null>(null);
  const [permission, setPermission] = useState<NotificationPermission | 'unsupported'>(() =>
    typeof Notification === 'undefined' ? 'unsupported' : Notification.permission);
  const vibration = typeof navigator !== 'undefined' && 'vibrate' in navigator;
  const [notificationError, setNotificationError] = useState(false);
  useEffect(() => {
    if ('serviceWorker' in navigator) void navigator.serviceWorker.register('/sw.js').catch(() => {});
    const available = (event: Event) => { event.preventDefault(); setInstall(event as InstallEvent); };
    const installed = () => setInstall(null);
    window.addEventListener('beforeinstallprompt', available);
    window.addEventListener('appinstalled', installed);
    return () => {
      window.removeEventListener('beforeinstallprompt', available);
      window.removeEventListener('appinstalled', installed);
    };
  }, []);
  return <SoftCard style={{ gap: 10, marginTop: 24 }}>
    <Text variant="titleMedium" accessibilityRole="header">{t('Listening in your browser')}</Text>
    <Text variant="bodyMedium" style={{ color: theme.colors.onSurfaceVariant }}>
      {t('Keep this page visible and your screen unlocked. Listening pauses when you hide this page.')}
    </Text>
    {!vibration && <Text variant="bodyMedium" style={{ color: theme.colors.onSurfaceVariant }}>
      {t('Vibration is unavailable in this browser. Visual alerts remain available.')}
    </Text>}
    {permission === 'granted' ? <Text variant="bodyMedium">{t('Browser notifications enabled')}</Text> :
      permission === 'default' ? <Button mode="outlined" icon="bell-outline" contentStyle={{ minHeight: 48 }}
        onPress={() => { void Notification.requestPermission().then(setPermission).catch(() => setNotificationError(true)); }}>
        {t('Enable browser notifications')}
      </Button> : <Text variant="bodyMedium" style={{ color: theme.colors.onSurfaceVariant }}>
        {t('Use on-screen alerts, or enable notifications in your browser site settings where supported.')}
      </Text>}
    {notificationError && <Text accessibilityRole="alert">{t('Could not enable browser notifications. Check your site settings.')}</Text>}
    {install && <Button mode="outlined" icon="download" contentStyle={{ minHeight: 48 }}
      onPress={() => { void install.prompt().then(() => install.userChoice).then(() => setInstall(null)).catch(() => setInstall(null)); }}>
      {t('Install CueBell')}
    </Button>}
    <View accessibilityRole="text">
      <Text variant="bodySmall" style={{ color: theme.colors.onSurfaceVariant }}>
        {t('You can add CueBell to your home screen from your browser menu. An internet connection is required.')}
      </Text>
    </View>
  </SoftCard>;
}
