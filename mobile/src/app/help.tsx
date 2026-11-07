import { ScrollView, StyleSheet, View } from 'react-native';
import { Icon, Text } from 'react-native-paper';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { ScreenHeader, SoftCard } from '../components/ui';
import { useAppTheme } from '../lib/theme';
import { useLanguage } from '../lib/i18n';

const steps = [
  { icon: 'microphone', title: 'Describe your listening task', body: 'Say or type what to listen for and when to alert you: a train arriving, boarding starting, your name being called, or another spoken event.' },
  { icon: 'ear-hearing', title: 'Check it', body: 'Check the subject, identifiers and event on screen. Nothing starts until you confirm.' },
  { icon: 'play-circle-outline', title: 'Tap Start Listening', body: 'Keep the phone near the speakers and the app notification visible.' },
];

const about = [
  { icon: 'cellphone-message', text: 'When speech matches your confirmed task, CueBell shows what was heard, vibrates and sounds an alarm, unless you ask for silent alerts.' },
  { icon: 'ear-hearing', text: 'CueBell listens to speech. It does not track live transport data, detect non-speech sounds, send messages or replace emergency warning systems.' },
  { icon: 'shield-lock-outline', text: 'Gnani Prisma processes microphone audio. OpenAI processes requests and announcement text. The app and relay save no recordings or transcripts on disk. Provider terms apply.' },
  { icon: 'cellphone-information', text: 'Android can interrupt listening in the background. Keep the microphone notification visible. This is an aid, not an official source.' },
];

export default function Help() {
  const { t } = useLanguage();
  const theme = useAppTheme();
  const insets = useSafeAreaInsets();
  const ink = { color: theme.colors.onSurface };
  const muted = { color: theme.colors.onSurfaceVariant };
  return <View style={[styles.root, { backgroundColor: theme.colors.background, paddingTop: insets.top }]}>
    <ScreenHeader title={t('Help')} />
    <ScrollView contentContainerStyle={[styles.content, { paddingBottom: Math.max(insets.bottom, 24) + 24 }]}>
      <Text variant="titleMedium" accessibilityRole="header" style={muted}>{t('How it works')}</Text>
      {steps.map((step, index) => <SoftCard key={step.title} style={styles.step}>
        <View style={[styles.number, { backgroundColor: theme.colors.primary }]}>
          <Text style={[styles.numberText, { color: theme.colors.onPrimary }]}>{index + 1}</Text>
        </View>
        <View style={styles.flex}>
          <Text variant="titleMedium" style={ink}>{t(step.title)}</Text>
          <Text variant="bodyMedium" style={muted}>{t(step.body)}</Text>
        </View>
        <Icon source={step.icon} size={28} color={theme.colors.onSurface} />
      </SoftCard>)}

      <Text variant="titleMedium" accessibilityRole="header" style={[muted, styles.gap]}>{t('About & privacy')}</Text>
      <SoftCard style={styles.about}>
        {about.map(item => <View key={item.icon} style={styles.row}>
          <Icon source={item.icon} size={24} color={theme.colors.onSurface} />
          <Text variant="bodyLarge" style={[styles.flex, ink]}>{t(item.text)}</Text>
        </View>)}
      </SoftCard>

      <View style={styles.row}>
        <Icon source="monitor-eye" size={22} color={theme.colors.onSurfaceVariant} />
        <Text variant="bodyMedium" style={[styles.flex, muted]}>{t('Events may be missed. Check the official source. Not an emergency alert system.')}</Text>
      </View>
    </ScrollView>
  </View>;
}

const styles = StyleSheet.create({
  root: { flex: 1 }, flex: { flex: 1, gap: 2 }, gap: { marginTop: 8 },
  content: { paddingHorizontal: 24, paddingTop: 8, gap: 16, maxWidth: 560, width: '100%', alignSelf: 'center' },
  step: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  number: { width: 40, height: 40, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  numberText: { fontSize: 20, fontWeight: '800' },
  about: { gap: 18 },
  row: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
});
