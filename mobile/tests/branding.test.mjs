import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const root = fileURLToPath(new URL('../../', import.meta.url));
const read = (name) => readFileSync(new URL(`../../${name}`, import.meta.url), 'utf8');
const origin = 'https://queuesaathi.mathewjoseph.xyz';

test('CueBell identity is consistent across app and package metadata', () => {
  const app = JSON.parse(read('mobile/app.json')).expo;
  const pkg = JSON.parse(read('mobile/package.json'));
  const lock = JSON.parse(read('mobile/package-lock.json'));
  assert.equal(app.name, 'CueBell');
  assert.equal(app.slug, 'cuebell');
  assert.equal(app.scheme, 'cuebell');
  assert.equal(app.android.package, 'app.cuebell.mobile');
  assert.equal(app.android.versionCode, 3);
  assert.equal(pkg.name, 'cuebell-mobile');
  assert.equal(pkg.version, app.version);
  assert.equal(lock.name, pkg.name);
  assert.equal(lock.version, pkg.version);
  assert.equal(lock.packages[''].name, pkg.name);
  assert.equal(lock.packages[''].version, pkg.version);
  assert.match(read('backend/pyproject.toml'), /^name = "cuebell"$/m);
  assert.match(read('backend/app/main.py'), /FastAPI\(title="CueBell relay"/);
});

test('rebranding preserves the operator-supplied backend and native alert identity', () => {
  const profiles = JSON.parse(read('mobile/eas.json')).build;
  for (const profile of ['preview', 'production']) {
    assert.equal(profiles[profile].env.EXPO_PUBLIC_API_URL, origin);
  }
  assert.match(read('mobile/src/app/index.tsx'), /title="CueBell"/);
  assert.match(read('mobile/src/lib/api.ts'), /'cuebell\.connection\.v1'/);
  const native = read('mobile/modules/queue-listener/android/src/main/java/expo/modules/queuelistener/ListenerService.kt');
  assert.match(native, /"CueBell · monitoring"/);
  assert.match(native, /"CueBell alert"/);
  assert.match(native, /"CueBell:Listening"/);
});

test('tracked source contains no legacy product name except the unchanged backend origin', () => {
  const files = execFileSync('git', ['ls-files', '-z'], { cwd: root, encoding: 'utf8' }).split('\0').filter(Boolean);
  const legacy = new RegExp('queue' + 'saathi', 'i');
  for (const name of files) {
    const bytes = readFileSync(new URL(`../../${name}`, import.meta.url));
    if (bytes.includes(0)) continue;
    const text = bytes.toString('utf8').replaceAll(origin, '');
    assert.equal(legacy.test(text), false, `Legacy branding in ${name}`);
  }
});
