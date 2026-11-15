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
    accessibilityHint={hint} accessibilityState={{ disabled: !!disabled, expanded }} aria-expanded={expanded} hitSlop={6}
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
        {corrected ? t('Alert changed') : alert.summary || t("It's your turn!")}</Text>
    </View>
    {corrected ? <Text variant="bodyLarge" style={{ color: s.ink }}>
      {t('Check the official source.')}
    </Text> : alert.summary ? (
      !!alert.location && !alert.summary.includes(alert.location) &&
      <Text variant="titleLarge" style={{ color: s.ink }}>{alert.location}</Text>
    ) : <>
      <Text testID="alert-token" selectable accessibilityLabel={`${t('Token')} ${spell(alert.token ?? '')}`}
        style={[styles.alertToken, { color: s.ink, fontSize: Math.round(44 * scale), lineHeight: Math.round(54 * scale) }]}>
        {alert.token}
      </Text>
      <Text style={[styles.alertCounter, { color: s.ink, fontSize: Math.round(26 * scale), lineHeight: Math.round(34 * scale) }]}>
        {alert.counter ? t('Counter {counter}', { counter: alert.counter }) : t('Counter unknown — check the display.')}</Text>
    </>}
    <Disclosure key={`${alert.id}:${alert.state}`} label={t('Details')} color={s.ink}>
      {corrected && <View style={{ gap: 4 }}>
        <Text variant="labelLarge" style={{ color: s.ink }}>{t('Previous alert')}</Text>
        <Text variant="bodyLarge" selectable style={{ color: s.ink }}>{alert.summary || t('Token {token}. {counter}', {
          token: alert.token ?? '', counter: alert.counter ? t('Counter {counter}', { counter: alert.counter }) : t('Counter unclear'),
        })}</Text>
      </View>}
      {!!alert.evidence_text && <View style={{ gap: 4 }}>
        <Text variant="labelLarge" style={{ color: s.ink }}>{t('What was heard')}</Text>
        <Text variant="bodyLarge" selectable style={{ color: s.ink }}>{alert.evidence_text}</Text>
      </View>}
      {!corrected && <Text variant="bodyMedium" style={{ color: s.ink }}>{t('Check the official source.')}</Text>}
    </Disclosure>
  </>;
}

/** Optional detail stays available to touch, keyboard and screen-reader users without filling the screen. */
export function Disclosure({ label, children, color, icon }: {
  label: string; children: ReactNode; color?: string; icon?: string;
}) {
  const [open, setOpen] = useState(false);
  const theme = useAppTheme();
  const ink = color ?? theme.colors.onSurface;
  return <View>
    <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ expanded: open }} aria-expanded={open}
      onPress={() => setOpen(value => !value)} style={styles.disclosure}>
      {icon && <Icon source={icon} size={24} color={ink} />}
      <Text variant="labelLarge" style={{ color: ink, flex: 1 }}>{label}</Text>
      <Icon source={open ? 'chevron-up' : 'chevron-down'} size={24} color={ink} />
    </Pressable>
    {open && <View style={styles.details}>{children}</View>}
  </View>;
}

export function AlertCard({ alert, onSeen, onOpen, busy }: { alert: QueueAlert; onSeen: () => void; onOpen: () => void; busy: boolean }) {
  const { t } = useLanguage();
  const theme = useAppTheme();
  const s = alert.state === 'corrected' ? theme.signal.changed : theme.signal.call;
  return <View style={[styles.alertCard, { backgroundColor: s.background, borderColor: s.edge, boxShadow: theme.shadow.soft }]}>
    <AlertBody alert={alert} />
    <Button mode="contained" icon="check-bold" buttonColor={s.ink} textColor={s.background} contentStyle={styles.bigAction}
      disabled={busy} onPress={onSeen}>{t('I’ve seen this')}</Button>
    <SoftIconButton icon="fullscreen" label={t('Show this alert full screen')} onPress={onOpen}
      style={{ alignSelf: 'flex-end' }} />
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
      <ScrollView contentContainerStyle={[styles.takeover, { paddingTop: insets.top + 32, paddingBottom: insets.bottom + 32 }]}>
        <AlertBody alert={alert} scale={1.15} />
        {more > 0 && <Text variant="titleMedium" style={{ color: s.ink }}
          accessibilityLabel={t('Additional alerts waiting: {count}', { count: more })}>+{more}</Text>}
        <View style={styles.takeoverActions}>
          <Button mode="contained" icon="check-bold" buttonColor={s.ink} textColor={s.background}
            contentStyle={styles.hugeAction} labelStyle={styles.hugeLabel} disabled={busy} onPress={onSeen}>{t('I’ve seen this')}</Button>
          <Button mode="text" icon="arrow-left" textColor={s.ink}
            contentStyle={styles.bigAction} accessibilityLabel={t('Back to app')} onPress={onLater}>{t('Back')}</Button>
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
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 6, borderRadius: 999, paddingHorizontal: 14, minHeight: 40 },
  notice: { flexDirection: 'row', alignItems: 'flex-start', gap: 12, padding: 16, borderRadius: 20, borderWidth: 1 },
  alertCard: { padding: 24, borderRadius: 28, borderWidth: 4, gap: 16 },
  alertHead: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  alertTitle: { fontWeight: '800', flexShrink: 1 },
  alertToken: { fontWeight: '800', fontVariant: ['tabular-nums'], writingDirection: 'ltr', textAlign: 'left' },
  alertCounter: { fontWeight: '700' },
  disclosure: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 48, paddingVertical: 8 },
  details: { gap: 12, paddingBottom: 12 },
  frame: { borderWidth: 14 },
  takeover: { width: '100%', maxWidth: 560, alignSelf: 'center', paddingHorizontal: 24, gap: 16, flexGrow: 1, justifyContent: 'center' },
  takeoverActions: { gap: 12, marginTop: 8 },
});
