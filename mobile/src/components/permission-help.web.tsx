import { Text } from 'react-native-paper';
import { useLanguage } from '../lib/i18n';

export function PermissionHelp() {
  const { t } = useLanguage();
  return <Text variant="bodyLarge" selectable>{t('Open the site controls beside the address bar to allow microphone access and notifications, then retry.')}</Text>;
}
