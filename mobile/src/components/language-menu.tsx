import { useState } from 'react';
import { ScrollView, StyleProp, View, ViewStyle, useWindowDimensions } from 'react-native';
import { Menu, Text } from 'react-native-paper';
import { languages, useLanguage } from '../lib/i18n';
import { SoftIconButton } from './ui';

/** Anchored, scrollable Material dropdown; dismisses with outside tap or Android Back. */
export function LanguageMenu({ style }: { style?: StyleProp<ViewStyle> }) {
  const { language, setLanguage, t, storageError } = useLanguage();
  const [visible, setVisible] = useState(false);
  const { height, width } = useWindowDimensions();
  return <View>
    <Menu visible={visible} onDismiss={() => setVisible(false)} overlayAccessibilityLabel={t('Close language menu')}
      anchor={<SoftIconButton icon="translate" label={t('App language: {language}', {
        language: languages.find(item => item.code === language)!.name,
      })} expanded={visible} style={style} onPress={() => setVisible(true)} />}>
      <ScrollView style={{ maxHeight: Math.max(144, height * 0.6), maxWidth: width - 48 }} keyboardShouldPersistTaps="handled">
        <Text variant="titleSmall" style={{ paddingHorizontal: 16, paddingVertical: 8 }}>{t('App language')}</Text>
        {languages.map(item => <Menu.Item key={item.code} title={item.name}
          testID={`language-${item.code}`} accessibilityLabel={item.name} accessibilityState={{ selected: item.code === language }}
          trailingIcon={item.code === language ? 'check' : undefined}
          onPress={() => { setLanguage(item.code); setVisible(false); }} />)}
        {storageError && <Text accessibilityLiveRegion="polite" style={{ padding: 16 }}>{t('Language could not be saved. Select it again to retry.')}</Text>}
      </ScrollView>
    </Menu>
  </View>;
}
