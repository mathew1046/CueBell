import { Linking } from 'react-native';
import { Button } from 'react-native-paper';
import { useLanguage } from '../lib/i18n';

export function PermissionHelp() {
  const { t } = useLanguage();
  return <Button mode="outlined" icon="cog-outline" contentStyle={{ minHeight: 48 }}
    onPress={() => void Linking.openSettings()}>{t('Open Android permissions')}</Button>;
}
