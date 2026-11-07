import { NativeModule, requireNativeModule } from 'expo';

declare class QueueListenerModule extends NativeModule<{
  onEvent: (event: { json: string }) => void;
}> {
  start(url: string, token: string, mode: 'request' | 'monitor'): Promise<void>;
  stop(): Promise<void>;
  snapshot(): string;
  clear(): void;
  dismissAlert(id: string): void;
  spokenAlertsEnabled(): boolean;
  setSpokenAlertsEnabled(enabled: boolean): void;
  setLanguage(language: string, catalog: string): void;
}

export default requireNativeModule<QueueListenerModule>('QueueListener');
