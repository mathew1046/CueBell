import { useLocalSearchParams } from 'expo-router';
import { ScrollView, StyleSheet, View } from 'react-native';
import { Icon, Text } from 'react-native-paper';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { ScreenHeader, SoftCard } from '../components/ui';
import { useAppTheme } from '../lib/theme';

const steps = [
  { icon: 'microphone', title: 'Say or type your token', body: 'Tap Start Listening on Home and say your token. Use the pencil to type it.' },
  { icon: 'ticket-confirmation-outline', title: 'Check it', body: 'Make sure the number on screen matches your slip.' },
  { icon: 'play-circle-outline', title: 'Tap Start Listening', body: 'Keep the phone near the speakers and the app notification visible.' },
];

const about = [
  { icon: 'cellphone-message', text: 'When your token is called the screen turns yellow, the phone vibrates and an alarm sounds, unless you ask for silent alerts.' },
  { icon: 'ticket-outline', text: 'Speak or type your token as the venue uses it.' },
  { icon: 'shield-lock-outline', text: 'Gnani Prisma processes microphone audio. OpenAI processes requests and announcement text. The app and relay save no recordings or transcripts on disk. Provider terms apply.' },
  { icon: 'cellphone-information', text: 'Android can interrupt listening in the background. Keep the microphone notification visible. This is an aid, not the official queue.' },
];

export default function Help() {
  const { topic } = useLocalSearchParams<{ topic?: string }>();
  const theme = useAppTheme();
  const insets = useSafeAreaInsets();
  const ink = { color: theme.colors.onSurface };
  const muted = { color: theme.colors.onSurfaceVariant };
  return <View style={[styles.root, { backgroundColor: theme.colors.background, paddingTop: insets.top }]}>
    <ScreenHeader title={topic === 'languages' ? 'Announcement languages' : 'Help'} />
    <ScrollView contentContainerStyle={[styles.content, { paddingBottom: Math.max(insets.bottom, 24) + 24 }]}>
      {topic === 'languages' && <SoftCard style={styles.step}>
        <Icon source="translate" size={28} color={theme.colors.onSurface} />
        <View style={styles.flex}>
          <Text variant="titleMedium" accessibilityRole="header" style={ink}>Language detection</Text>
          <Text variant="bodyMedium" style={muted}>
            CueBell captions announcements using the languages configured for its speech service.
          </Text>
        </View>
      </SoftCard>}
      <Text variant="titleMedium" accessibilityRole="header" style={muted}>How it works</Text>
      {steps.map((step, index) => <SoftCard key={step.title} style={styles.step}>
        <View style={[styles.number, { backgroundColor: theme.colors.primary }]}>
          <Text style={[styles.numberText, { color: theme.colors.onPrimary }]}>{index + 1}</Text>
        </View>
        <View style={styles.flex}>
          <Text variant="titleMedium" style={ink}>{step.title}</Text>
          <Text variant="bodyMedium" style={muted}>{step.body}</Text>
        </View>
        <Icon source={step.icon} size={28} color={theme.colors.onSurface} />
      </SoftCard>)}

      <Text variant="titleMedium" accessibilityRole="header" style={[muted, styles.gap]}>About & privacy</Text>
      <SoftCard style={styles.about}>
        {about.map(item => <View key={item.icon} style={styles.row}>
          <Icon source={item.icon} size={24} color={theme.colors.onSurface} />
          <Text variant="bodyLarge" style={[styles.flex, ink]}>{item.text}</Text>
        </View>)}
      </SoftCard>

      <View style={styles.row}>
        <Icon source="monitor-eye" size={22} color={theme.colors.onSurfaceVariant} />
        <Text variant="bodyMedium" style={[styles.flex, muted]}>Calls may be missed. Check the venue display.</Text>
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
