import { useRouter } from 'expo-router';
import { ReactNode, useEffect, useState } from 'react';
import { Animated, Modal, Pressable, ScrollView, StyleProp, StyleSheet, View, ViewStyle } from 'react-native';
import { Button, Icon, Text } from 'react-native-paper';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { spell } from '../lib/a11y';
import { useLanguage } from '../lib/i18n';
import { useAppTheme } from '../lib/theme';
import { Preference, QueueAlert } from '../lib/types';

/** Slow opacity pulse (well under 3 flashes per second). Disabled when the user asks for reduced motion. */
export function usePulse(active: boolean, duration = 900) {
  const [value] = useState(() => new Animated.Value(1));
  useEffect(() => {
    if (!active) { value.setValue(1); return; }
    const loop = Animated.loop(Animated.sequence([
      Animated.timing(value, { toValue: 0.25, duration, useNativeDriver: true }),
      Animated.timing(value, { toValue: 1, duration, useNativeDriver: true }),
    ]));
    loop.start();
    return () => loop.stop();
  }, [active, duration, value]);
  return value;
}

export type Tone = 'live' | 'warn' | 'idle';

/** Raised soft surface: paired highlight and shadow on the warm paper background. */
export function SoftCard({ children, style }: { children: ReactNode; style?: StyleProp<ViewStyle> }) {
  const theme = useAppTheme();
  return <View style={[styles.card, { backgroundColor: theme.colors.surface, boxShadow: theme.shadow.soft }, style]}>{children}</View>;
}

/** Small square soft button (edit, back). Always has a spoken label. */
export function SoftIconButton({ icon, label, onPress, disabled, hint, style, expanded }: {
  icon: string; label: string; onPress: () => void; disabled?: boolean; hint?: string;
  style?: StyleProp<ViewStyle>; expanded?: boolean;
}) {
  const theme = useAppTheme();
  return <Pressable onPress={onPress} disabled={disabled} accessibilityRole="button" accessibilityLabel={label}
    accessibilityHint={hint} accessibilityState={{ disabled: !!disabled, expanded }} hitSlop={6}
    style={({ pressed }) => [styles.iconButton, { backgroundColor: theme.colors.surfaceVariant,
      boxShadow: pressed ? theme.shadow.inset : undefined, opacity: disabled ? 0.45 : 1 }, style]}>
    <Icon source={icon} size={26} color={theme.colors.onSurface} />
  </Pressable>;
}

/** Large navigation tile: icon above a short word. */
export function NavTile({ icon, label, onPress, badge }: { icon: string; label: string; onPress: () => void; badge?: string }) {
  const theme = useAppTheme();
  return <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel={badge ? `${label}, ${badge}` : label}
    style={({ pressed }) => [styles.tile, { backgroundColor: theme.colors.surface,
      boxShadow: pressed ? theme.shadow.inset : theme.shadow.soft }]}>
    <Icon source={icon} size={36} color={theme.colors.onSurface} />
    <Text variant="titleMedium" style={{ color: theme.colors.onSurface, textAlign: 'center', width: '100%', flexShrink: 1 }}>{label}</Text>
    {!!badge && <View style={[styles.badge, { backgroundColor: theme.colors.primary }]}>
      <Text style={[styles.badgeText, { color: theme.colors.onPrimary }]}>{badge}</Text>
    </View>}
  </Pressable>;
}

/** Sub-screen header: back, title, and a compact microphone state so listening health is never hidden. */
export function ScreenHeader({ title, status }: { title: string; status?: { tone: Tone; icon: string; label: string } }) {
  const { t } = useLanguage();
  const theme = useAppTheme();
  const router = useRouter();
  const s = status && theme.signal[status.tone];
  return <View style={styles.header}>
    <SoftIconButton icon="arrow-left" label={t('Back')} onPress={() => {
      if (router.canGoBack()) router.back();
      else router.replace('/');
    }} />
    <Text variant="headlineSmall" accessibilityRole="header" style={[styles.flex, { color: theme.colors.onSurface }]}>{title}</Text>
    {status && s && <View accessible accessibilityLabel={t('Microphone: {status}', { status: status.label })}
      style={[styles.pill, { backgroundColor: s.background, borderColor: s.edge }]}>
      <Icon source={status.icon} size={18} color={s.ink} />
      <Text variant="labelLarge" style={{ color: s.ink, flexShrink: 1 }}>{status.label}</Text>
    </View>}
  </View>;
}

/** Each character in its own tile: prefixes and leading zeros stay visible and checkable. */
export function TokenTiles({ token, size = 56, ink, tile, edge, label }: {
  token: string; size?: number; ink?: string; tile?: string; edge?: string; label?: string;
}) {
  const theme = useAppTheme();
  const { t } = useLanguage();
  return <View accessible accessibilityRole="text" accessibilityLabel={`${label ?? t('Token')} ${spell(token)}`} style={styles.tiles}>
    {token.split('').map((char, index) => <View key={index} style={[styles.tokenTile, {
      minWidth: size * 0.82, borderRadius: Math.round(size * 0.2), borderColor: edge ?? theme.colors.onSurface,
      backgroundColor: tile ?? theme.colors.surface }]}>
      <Text style={[styles.tileText, { fontSize: size, lineHeight: Math.round(size * 1.18), color: ink ?? theme.colors.onSurface }]}>{char}</Text>
    </View>)}
  </View>;
}

const prefIcons: Record<string, string> = { visual: 'eye-outline', vibration: 'vibrate', sound: 'alarm-bell' };

export function PrefChips({ values }: { values: Preference[] }) {
  const theme = useAppTheme();
  const { t } = useLanguage();
  const labels = { visual: t('On screen'), vibration: t('Vibrate'), sound: t('Alarm sound') };
  return <View accessible accessibilityLabel={t('Alert by: {preferences}', { preferences: values.map(value => labels[value]).join(', ') })} style={styles.chips}>
    {values.map(value => <View key={value} style={[styles.chip, { backgroundColor: theme.colors.surfaceVariant }]}>
      <Icon source={prefIcons[value] ?? 'bell-outline'} size={20} color={theme.colors.onSurface} />
      <Text variant="bodyMedium" style={{ color: theme.colors.onSurface, fontWeight: '600' }}>{labels[value]}</Text>
    </View>)}
  </View>;
}

/** Inline message with an icon, never colour alone. */
export function Notice({ tone, icon, children, live, role }: {
  tone: 'info' | 'warn' | 'error'; icon: string; children: ReactNode; live?: 'polite' | 'assertive'; role?: 'alert';
}) {
  const theme = useAppTheme();
  const c = tone === 'error' ? { background: theme.colors.errorContainer, ink: theme.colors.onErrorContainer, edge: theme.colors.error } :
    tone === 'warn' ? theme.signal.warn : { background: theme.colors.surfaceVariant, ink: theme.colors.onSurface, edge: theme.colors.surfaceVariant };
  return <View accessible accessibilityRole={role} accessibilityLiveRegion={live}
    style={[styles.notice, { backgroundColor: c.background, borderColor: c.edge }]}>
    <Icon source={icon} size={24} color={c.ink} />
    <Text variant="bodyLarge" style={[styles.flex, { color: c.ink }]}>{children}</Text>
  </View>;
}

function AlertBody({ alert, scale = 1 }: { alert: QueueAlert; scale?: number }) {
  const { t } = useLanguage();
  const theme = useAppTheme();
  const corrected = alert.state === 'corrected';
  const s = corrected ? theme.signal.changed : theme.signal.call;
  return <>
    <View accessible accessibilityRole="header" style={styles.alertHead}>
      <Icon source={corrected ? 'alert-octagon' : 'bell-ring'} size={Math.round(36 * scale)} color={s.ink} />
      <Text style={[styles.alertTitle, { color: s.ink, fontSize: Math.round(30 * scale), lineHeight: Math.round(38 * scale) }]}>
        {corrected ? t('Alert changed') : alert.summary ? t('Event detected') : t("It's your turn!")}</Text>
    </View>
    {alert.summary ? <>
      <Text style={[styles.alertCounter, { color: s.ink, fontSize: Math.round(24 * scale), lineHeight: Math.round(34 * scale) }]}>{alert.summary}</Text>
      {corrected && <Text variant="bodyLarge" style={{ color: s.ink }}>{t('This alert was corrected or cancelled. Do not rely on the previous announcement.')}</Text>}
      {!!alert.location && <Text variant="titleLarge" style={{ color: s.ink }}>{t('Location: {location}', { location: alert.location })}</Text>}
      {!!alert.evidence_text && <View style={{ gap: 4 }}>
        <Text variant="labelLarge" style={{ color: s.ink }}>{t('What was heard')}</Text>
        <Text variant="bodyLarge" selectable style={{ color: s.ink }}>{alert.evidence_text}</Text>
      </View>}
    </> : <>
    <TokenTiles token={alert.token ?? ''} size={Math.round(60 * scale)} ink={s.ink} tile="#FFFFFF" edge={s.edge} />
    <Text style={[styles.alertCounter, { color: s.ink, fontSize: Math.round(26 * scale), lineHeight: Math.round(34 * scale) }]}>
      {corrected ? t('Previous call corrected or cancelled.') : alert.counter ? t('Go to counter {counter}', { counter: alert.counter }) : t('Counter unclear')}</Text>
    </>}
    <View style={styles.alertNote}>
      <Icon source="monitor-eye" size={22} color={s.ink} />
      <Text variant="bodyLarge" style={[styles.flex, { color: s.ink }]}>{t('Check the official source.')}</Text>
    </View>
  </>;
}

export function AlertCard({ alert, onSeen, onOpen, busy }: { alert: QueueAlert; onSeen: () => void; onOpen: () => void; busy: boolean }) {
  const { t } = useLanguage();
  const theme = useAppTheme();
  const s = alert.state === 'corrected' ? theme.signal.changed : theme.signal.call;
  return <View style={[styles.alertCard, { backgroundColor: s.background, borderColor: s.edge, boxShadow: theme.shadow.soft }]}>
    <AlertBody alert={alert} />
    <Button mode="contained" icon="check-bold" buttonColor={s.ink} textColor={s.background} contentStyle={styles.bigAction}
      disabled={busy} onPress={onSeen}>{t('I’ve seen this')}</Button>
    <Button mode="text" icon="fullscreen" textColor={s.ink} contentStyle={styles.action} onPress={onOpen}
      accessibilityLabel={t('Show this alert full screen')}>{t('Full screen')}</Button>
  </View>;
}

/** Full-screen visual call for people who cannot hear the announcement. Back returns to the app; the card stays. */
export function AlertTakeover({ alert, more, visible, busy, reduceMotion, onSeen, onLater }: {
  alert?: QueueAlert; more: number; visible: boolean; busy: boolean; reduceMotion: boolean;
  onSeen: () => void; onLater: () => void;
}) {
  const theme = useAppTheme();
  const insets = useSafeAreaInsets();
  const { t } = useLanguage();
  const pulse = usePulse(visible && !reduceMotion, 700);
  if (!alert) return null;
  const s = alert.state === 'corrected' ? theme.signal.changed : theme.signal.call;
  return <Modal visible={visible} animationType="none" statusBarTranslucent navigationBarTranslucent onRequestClose={onLater}>
    <View style={[styles.flex, { backgroundColor: s.background }]}>
      <Animated.View pointerEvents="none" style={[StyleSheet.absoluteFill, styles.frame, { borderColor: s.edge, opacity: pulse }]} />
      <ScrollView contentContainerStyle={[styles.takeover, { paddingTop: insets.top + 40, paddingBottom: insets.bottom + 32 }]}>
        <AlertBody alert={alert} scale={1.3} />
        {more > 0 && <Text variant="titleMedium" style={{ color: s.ink }}>{t('Additional alerts waiting: {count}', { count: more })}</Text>}
        <View style={styles.takeoverActions}>
          <Button mode="contained" icon="check-bold" buttonColor={s.ink} textColor={s.background}
            contentStyle={styles.hugeAction} labelStyle={styles.hugeLabel} disabled={busy} onPress={onSeen}>{t('I’ve seen this')}</Button>
          <Button mode="outlined" icon="arrow-left" textColor={s.ink} style={{ borderColor: s.ink, borderWidth: 2 }}
            contentStyle={styles.bigAction} onPress={onLater}>{t('Back to app')}</Button>
        </View>
      </ScrollView>
    </View>
  </Modal>;
}

export const actionStyles = StyleSheet.create({
  action: { minHeight: 56 },
  big: { minHeight: 64 },
});

const styles = StyleSheet.create({
  flex: { flex: 1, gap: 2 },
  action: actionStyles.action,
  bigAction: actionStyles.big,
  hugeAction: { minHeight: 80 },
  hugeLabel: { fontSize: 24, lineHeight: 30, fontWeight: '700' },
  card: { borderRadius: 28, padding: 20 },
  iconButton: { width: 56, height: 56, borderRadius: 18, alignItems: 'center', justifyContent: 'center' },
  tile: { flex: 1, minHeight: 112, borderRadius: 28, alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 16, paddingHorizontal: 6 },
  badge: { position: 'absolute', top: 10, right: 10, minWidth: 24, height: 24, borderRadius: 12, paddingHorizontal: 6, alignItems: 'center', justifyContent: 'center' },
  badgeText: { fontSize: 13, fontWeight: '800' },
  header: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 16, paddingHorizontal: 20, paddingVertical: 12 },
  pill: { flexDirection: 'row', maxWidth: '100%', flexShrink: 1, alignItems: 'center', gap: 6, borderRadius: 999, borderWidth: 1, paddingHorizontal: 12, minHeight: 36 },
  tiles: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  tokenTile: { borderWidth: 3, paddingHorizontal: 8, paddingVertical: 4, alignItems: 'center', justifyContent: 'center' },
  tileText: { fontWeight: '800', fontVariant: ['tabular-nums'], includeFontPadding: false, textAlign: 'center' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 6, borderRadius: 999, paddingHorizontal: 14, minHeight: 40 },
  notice: { flexDirection: 'row', alignItems: 'flex-start', gap: 12, padding: 16, borderRadius: 20, borderWidth: 1 },
  alertCard: { padding: 24, borderRadius: 28, borderWidth: 4, gap: 16 },
  alertHead: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  alertTitle: { fontWeight: '800', flexShrink: 1 },
  alertCounter: { fontWeight: '700' },
  alertNote: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  frame: { borderWidth: 14 },
  takeover: { paddingHorizontal: 32, gap: 24, flexGrow: 1, justifyContent: 'center' },
  takeoverActions: { gap: 12, marginTop: 8 },
});
