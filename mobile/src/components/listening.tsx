import { requireNativeView } from 'expo';
import { ComponentRef, useRef, useState } from 'react';
import { NativeScrollEvent, NativeSyntheticEvent, ScrollView, StyleSheet, View, ViewProps } from 'react-native';
import { Button, Text } from 'react-native-paper';
import type { QueueEvent } from '../lib/types';
import { useAppTheme } from '../lib/theme';

const NativeWaveform = requireNativeView<ViewProps & { animate: boolean; barColor: string }>('QueueListener');

export function ListeningWaveform({ animate, color, height }: { animate: boolean; color: string; height: number }) {
  return <NativeWaveform animate={animate} barColor={color}
    importantForAccessibility="no-hide-descendants" pointerEvents="none"
    style={{ width: '100%', height }} />;
}

export function LiveTranscription({ events, listening, mode }: {
  events: QueueEvent[]; listening: boolean; mode: 'request' | 'monitor';
}) {
  const theme = useAppTheme();
  const viewport = useRef<ComponentRef<typeof ScrollView>>(null);
  const follow = useRef(true);
  const [awayFromLatest, setAwayFromLatest] = useState(false);
  const transcripts = events.filter(event => event.type === 'transcript' && event.mode === mode && event.segment).reverse();
  const placeholder = mode === 'request' ? 'Your spoken token request will appear here.' :
    listening ? 'Waiting for announcements...' : 'Announcements will appear here.';

  const onScroll = ({ nativeEvent }: NativeSyntheticEvent<NativeScrollEvent>) => {
    const nearEnd = nativeEvent.contentSize.height - nativeEvent.layoutMeasurement.height - nativeEvent.contentOffset.y < 32;
    follow.current = nearEnd;
    setAwayFromLatest(!nearEnd);
  };

  return <View style={styles.section}>
    <Text variant="titleLarge" accessibilityRole="header" style={{ color: theme.colors.onSurface }}>Live Transcription</Text>
    <View style={[styles.panel, { backgroundColor: theme.colors.surface, borderColor: theme.colors.outlineVariant }]}>
      {transcripts.length ? <ScrollView ref={viewport} nestedScrollEnabled style={styles.viewport}
        contentContainerStyle={styles.lines} onScroll={onScroll} scrollEventThrottle={32}
        onContentSizeChange={() => { if (follow.current) viewport.current?.scrollToEnd({ animated: false }); }}>
        {transcripts.map(({ segment }) => segment && <Text key={segment.id} selectable variant="bodyLarge"
          style={{ color: theme.colors.onSurface }}>{segment.text}</Text>)}
      </ScrollView> : <Text variant="bodyLarge" style={[styles.placeholder, { color: theme.colors.onSurfaceVariant }]}>
        {placeholder}
      </Text>}
    </View>
    {transcripts.length > 0 && awayFromLatest && <Button mode="text" icon="arrow-down" contentStyle={styles.jump}
      onPress={() => {
        follow.current = true;
        setAwayFromLatest(false);
        viewport.current?.scrollToEnd({ animated: false });
      }}>Jump to latest</Button>}
  </View>;
}

const styles = StyleSheet.create({
  section: { gap: 10 },
  panel: { borderWidth: 1, borderRadius: 16 },
  viewport: { maxHeight: 200 },
  lines: { gap: 12, padding: 16 },
  placeholder: { padding: 16 },
  jump: { minHeight: 48 },
});
