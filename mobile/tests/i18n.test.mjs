import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import ts from 'typescript';
import catalogs from '../src/lib/i18n/catalogs.json' with { type: 'json' };
import source from '../src/lib/i18n/en.json' with { type: 'json' };
import { languages, isLanguage } from '../src/lib/i18n/languages.ts';
import { translate, translateServiceMessage } from '../src/lib/i18n/translate.ts';

const placeholders = text => [...text.matchAll(/\{(\w+)\}/g)].map(match => match[1]).sort();
test('every selectable language has a complete stored catalog with safe placeholders', () => {
  assert.equal(languages.length, 21);
  assert.ok(isLanguage('hi'));
  assert.equal(isLanguage('invalid'), false);
  assert.equal(isLanguage(null), false);
  assert.deepEqual(Object.keys(catalogs).sort(), languages.map(item => item.code).sort());
  for (const { code } of languages) {
    assert.deepEqual(Object.keys(catalogs[code]).sort(), Object.keys(source).sort(), code);
    for (const message of Object.keys(source)) {
      assert.ok(catalogs[code][message].trim(), `${code}: ${message}`);
      assert.deepEqual(placeholders(catalogs[code][message]), placeholders(message), `${code}: ${message}`);
    }
    if (code !== 'en') assert.notEqual(translate(code, 'Start Listening'), 'Start Listening', code);
  }
});

test('language switches leave token identifiers and leading zeros intact', () => {
  for (const { code } of languages) {
    assert.ok(translate(code, '{label}, {token}', { label: translate(code, 'Token'), token: 'P042' }).includes('P042'));
    assert.ok(translate(code, 'Go to counter {counter}', { counter: '007' }).includes('007'));
  }
  assert.ok(translate('ur', 'Counter {counter}', { counter: 'A007' }).includes('\u2068A007\u2069'));
  assert.equal(translate('en', 'Unknown {value}', { value: '001' }), 'Unknown 001');
  assert.equal(translate('hi', 'Unknown {value}'), 'Unknown {value}');
});

test('service status templates localize without translating or leaking private runtime text', () => {
  const fallback = 'Something went wrong. Please try again.';
  assert.equal(translateServiceMessage('en', 'Original server detail', fallback), 'Original server detail');
  assert.equal(translateServiceMessage('hi', 'Listening again after a 3s gap. Check the display.', fallback),
    translate('hi', 'Listening again after a {seconds}s gap. Check the display.', { seconds: 3 }));
  const retry = translateServiceMessage('hi', 'Private server response Retrying in 4s.', fallback);
  assert.ok(retry.includes(translate('hi', 'Retrying in {seconds}s.', { seconds: 4 })));
  assert.equal(retry.includes('Private server response'), false);
});

test('language button opens a dropdown, not the removed announcement languages page', () => {
  const home = readFileSync(new URL('../src/app/index.tsx', import.meta.url), 'utf8');
  const help = readFileSync(new URL('../src/app/help.tsx', import.meta.url), 'utf8');
  assert.ok(home.includes('<LanguageMenu'));
  assert.equal(home.includes('topic=languages'), false);
  assert.equal(help.includes('Announcement Languages'), false);
  const provider = readFileSync(new URL('../src/lib/i18n/index.tsx', import.meta.url), 'utf8');
  assert.ok(provider.includes('SecureStore.setItemAsync(KEY, next)'));
  assert.ok(provider.includes('Listener.setLanguage(language'));
});

test('all literal translation calls are present in the stored English catalog', () => {
  // AST traversal handles apostrophes/escaped content, not just regex string matching.
  const config = ts.readConfigFile(new URL('../tsconfig.json', import.meta.url).pathname, ts.sys.readFile);
  const parsed = ts.parseJsonConfigFileContent(config.config, ts.sys, new URL('..', import.meta.url).pathname);
  for (const file of parsed.fileNames.filter(file => file.includes('/src/') && !file.includes('/i18n/'))) {
    const node = ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true);
    function visit(child) {
      if (ts.isCallExpression(child) && child.expression.getText(node) === 't' && child.arguments[0] && ts.isStringLiteral(child.arguments[0])) {
        assert.ok(Object.hasOwn(source, child.arguments[0].text), `${file}: ${child.arguments[0].text}`);
      }
      ts.forEachChild(child, visit);
    }
    visit(node);
  }
});

test('token notifications include the bundled alarm and independently honor vibration/sound preferences', () => {
  const service = readFileSync(new URL('../modules/queue-listener/android/src/main/java/expo/modules/queuelistener/ListenerService.kt', import.meta.url), 'utf8');
  assert.ok(service.includes('calls-v3-'));
  assert.ok(service.includes('android.resource://$packageName/raw/cuebell_alarm'));
  assert.ok(service.includes('if (sound) alarmSound else null'));
  assert.ok(service.includes('enableVibration(vibration)'));
  assert.ok(service.includes('.setOnlyAlertOnce(silent)'));
  const audio = readFileSync(new URL('../modules/queue-listener/android/src/main/res/raw/cuebell_alarm.wav', import.meta.url));
  assert.equal(audio.toString('ascii', 0, 4), 'RIFF');
  assert.equal(audio.toString('ascii', 8, 12), 'WAVE');
  assert.equal(audio.readUInt32LE(24), 22050);
  assert.equal(audio.readUInt32LE(40) / (22050 * 2), 2.4);
});
