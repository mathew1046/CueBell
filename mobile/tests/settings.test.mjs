import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import { compileFunction } from 'node:vm';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ts from 'typescript';
import { stopListening } from '../src/lib/stop-listening.ts';

const require = createRequire(import.meta.url);
const source = readFileSync(new URL('../src/app/settings.tsx', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
});
const loadSettings = compileFunction(outputText, ['exports', 'require']);

function renderSettings(app) {
  const buttons = new Map();
  const container = ({ children }) => children;
  const empty = () => null;
  const modules = {
    'expo-router': { useLocalSearchParams: () => ({}) },
    'react-native': { View: container, ScrollView: container, Pressable: container,
      StyleSheet: { create: styles => styles }, Linking: {} },
    'react-native-paper': {
      Text: container, Icon: empty, Switch: empty,
      Button: ({ children, disabled, onPress }) => {
        buttons.set(children, { disabled, onPress });
        return createElement('button', { disabled }, children);
      },
    },
    'react-native-safe-area-context': { useSafeAreaInsets: () => ({ top: 0, bottom: 0 }) },
    '../../modules/queue-listener': { __esModule: true, default: { spokenAlertsEnabled: () => false } },
    '../components/app': { ConsentCard: empty, ErrorBanner: empty },
    '../components/ui': { actionStyles: {}, ScreenHeader: empty, SoftCard: container },
    '../lib/a11y': { spell: token => token },
    '../lib/cuebell': { useCueBell: () => app },
    '../lib/theme': { useAppTheme: () => ({ colors: {}, shadow: {} }) },
    '../lib/themeMode': { useThemeMode: () => ({ mode: 'system' }) },
  };
  const exports = {};
  loadSettings(exports, id => modules[id] ?? require(id));
  const html = renderToStaticMarkup(createElement(exports.default));
  return { buttons, html };
}

test('Settings can retry Stop after a storage failure clears the active token', async () => {
  let connection = { url: 'https://example.org', token: 'test-bearer', expires: 9999999999 };
  let saved = connection;
  let storageAvailable = false;
  const app = { activeRule: { token: '42' }, storageCleanupPending: false, native: { running: false }, busy: false };
  app.stop = () => stopListening('stop', connection, {
    stopCapture: async () => {},
    clearLocal: () => { app.activeRule = null; },
    setStorageCleanupPending: pending => { app.storageCleanupPending = pending; },
    setConnection: next => { connection = next; },
    save: async next => {
      if (!storageAvailable) throw new Error('storage unavailable');
      saved = next;
    },
    remove: async () => { throw new Error('storage unavailable'); },
    remote: async () => {},
  });

  const watching = renderSettings(app);
  assert.match(watching.html, /<button>Stop<\/button>/);
  await assert.rejects(watching.buttons.get('Stop').onPress(), /Retry Stop in Settings/);

  const stopped = renderSettings(app);
  assert.match(stopped.html, /No token is being watched/);
  assert.match(stopped.html, /<button>Retry Stop<\/button>/);
  assert.equal(renderSettings({ ...app, busy: true }).buttons.get('Retry Stop').disabled, true);

  storageAvailable = true;
  await stopped.buttons.get('Retry Stop').onPress();
  assert.equal(saved.suppressMonitor, true);
  const recovered = renderSettings(app);
  assert.equal(recovered.buttons.has('Retry Stop'), false);
  assert.equal(recovered.buttons.has('Stop'), false);
});
