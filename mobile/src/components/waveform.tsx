import { requireNativeView } from 'expo';
import type { ViewProps } from 'react-native';

const NativeWaveform = requireNativeView<ViewProps & { animate: boolean; barColor: string }>('QueueListener');

export function ListeningWaveform({ animate, color, height }: { animate: boolean; color: string; height: number }) {
  return <NativeWaveform animate={animate} barColor={color}
    importantForAccessibility="no-hide-descendants" pointerEvents="none"
    style={{ width: '100%', height }} />;
}
