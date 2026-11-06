import { ScrollView, StyleSheet, View } from 'react-native';
import { Icon, Text } from 'react-native-paper';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Notice, ScreenHeader, SoftCard } from '../components/ui';
import { useCueBell } from '../lib/cuebell';
import { useAppTheme } from '../lib/theme';

export default function History() {
  const theme = useAppTheme();
  const insets = useSafeAreaInsets();
  const app = useCueBell();
  const muted = { color: theme.colors.onSurfaceVariant };
  return <View style={[styles.root, { backgroundColor: theme.colors.background, paddingTop: insets.top }]}>
    <ScreenHeader title="History" status={{ tone: app.tone, icon: app.statusIcon, label: app.statusLabel }} />
    <ScrollView contentContainerStyle={[styles.content, { paddingBottom: Math.max(insets.bottom, 24) + 24 }]}>
      <Text variant="bodyMedium" style={muted} accessibilityRole="header">Announcements</Text>
      {app.latestUnclear && <Notice tone="warn" icon="help-circle" live="polite">Unclear announcement. Check the display.</Notice>}
      {app.events.length === 0 ? <SoftCard style={styles.empty}>
        <Icon source="history" size={40} color={theme.colors.onSurfaceVariant} />
        <Text variant="bodyLarge" style={muted}>No announcements yet.</Text>
      </SoftCard> : app.events.slice(0, 30).map((event, index) => {
        const uncertain = event.observation?.type === 'UNCERTAIN';
        return <SoftCard key={event.segment?.id ?? event.observation?.id ?? index}
          style={[styles.item, uncertain && { borderWidth: 2, borderColor: theme.signal.warn.edge }]}>
          <View style={[styles.itemIcon, { backgroundColor: theme.colors.surfaceVariant }]}>
            <Icon source={event.segment ? (event.mode === 'request' ? 'account-voice' : 'text-box-outline') :
              uncertain ? 'help-circle' : 'bullhorn-outline'} size={24} color={theme.colors.onSurface} />
          </View>
          <View style={styles.flex}>
            {event.segment ? <>
              <Text variant="labelLarge" style={muted}>{event.mode === 'request' ? 'Your spoken request' : 'Announcement transcript'}</Text>
              <Text variant="bodyLarge" selectable style={{ color: theme.colors.onSurface }}>{event.segment.text}</Text>
            </> : event.observation && <>
              <Text variant="titleMedium" style={{ color: theme.colors.onSurface }}>{uncertain ? 'Uncertain · check the display' :
                `${event.observation.type.toLowerCase()} · ${event.observation.token_normalized ?? 'no token'}`}</Text>
              <Text variant="bodyMedium" style={muted}>{event.observation.ambiguity_reason ??
                (event.observation.counter ? `Counter ${event.observation.counter}` : 'Counter not identified')}</Text>
            </>}
          </View>
        </SoftCard>;
      })}
    </ScrollView>
  </View>;
}

const styles = StyleSheet.create({
  root: { flex: 1 }, flex: { flex: 1, gap: 4 },
  content: { paddingHorizontal: 24, paddingTop: 8, gap: 16, maxWidth: 560, width: '100%', alignSelf: 'center' },
  empty: { alignItems: 'center', gap: 12, paddingVertical: 40 },
  item: { flexDirection: 'row', gap: 14, alignItems: 'flex-start' },
  itemIcon: { width: 44, height: 44, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
});
