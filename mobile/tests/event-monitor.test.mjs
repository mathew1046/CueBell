import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8');

test('home accepts a confirmed general task without a queue token', () => {
  const home = read('../src/app/index.tsx');
  assert.ok(home.includes('const hasTask = !!(task || token)'));
  assert.ok(home.includes('task?.summary ?? token'));
  assert.equal(home.includes('if (!token)'), false);
  assert.equal(home.includes("t('Review task')"), false);
  assert.ok(home.includes("t('Listening task')"));
});

test('valid setup activates immediately and cancelled setup cannot start the microphone later', () => {
  const state = read('../src/lib/cuebell.tsx');
  assert.match(state, /await activateProposal\(result\.proposal_id, current\)/);
  assert.match(state, /const current = \(\) => setupAttempt\.current === attempt && consentRef\.current/);
  assert.match(state, /await startListeningIfCurrent/);
  assert.match(state, /return allowed\(\)/);
  assert.match(state, /\['STOPPING', 'STOPPED', 'ERROR'\].includes/);
  assert.equal(state.includes('Nothing has started yet'), false);
  const home = read('../src/app/index.tsx');
  assert.match(home, /const showTranscript = showRequest \|\| \(captureInProgress && captionsOpen\)/);
  assert.equal(home.includes('spokenSetup'), false);
  assert.match(home, /disabled=\{stopping\}/);
});

test('request handoff keeps the foreground service but releases audio and closes the old stream', () => {
  const service = read('../modules/queue-listener/android/src/main/java/expo/modules/queuelistener/ListenerService.kt');
  const request = service.slice(service.indexOf('"transcript" ->'), service.indexOf('"monitor.pause", "monitor.stop" ->'));
  assert.match(request, /generation\+\+/);
  assert.match(request, /stopCapture\(\)/);
  assert.match(request, /socket\?\.close\(1000, null\)/);
  assert.match(request, /status\("PROCESSING"/);
  assert.equal(request.includes('stopSelf()'), false);
  assert.match(request, /postDelayed\(processingTimeout, 150000\)/);
  assert.match(service, /waitingForTask &&/);
  assert.match(service, /if \(!stopping && waitingForTask\)/);
});

test('setup asks for the listening goal and condition, not a required token', () => {
  const setup = read('../src/app/token.tsx');
  assert.equal(setup.includes('Say your token'), false);
  assert.ok(setup.includes('train 14922'));
  assert.ok(setup.includes('What should I listen for?'));
});

test('event alert has summary and verbatim evidence with a separate legacy token branch', () => {
  const ui = read('../src/components/ui.tsx');
  assert.ok(ui.includes('alert.summary ?'));
  assert.ok(ui.includes('alert.evidence_text'));
  assert.ok(ui.includes("t('What was heard')"));
  assert.ok(ui.includes('alert.location'));
  const native = read('../modules/queue-listener/android/src/main/java/expo/modules/queuelistener/ListenerService.kt');
  assert.equal(native.includes('alert.getString("token")'), false);
  assert.ok(native.includes('alert.optString("summary"'));
  assert.ok(native.includes('Event detected'));
});
