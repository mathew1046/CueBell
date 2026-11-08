import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const root = fileURLToPath(new URL('../../', import.meta.url));
const read = (name) => readFileSync(new URL(`../../${name}`, import.meta.url), 'utf8');
const origin = 'https://cuebell.mathewjoseph.xyz';

test('CueBell identity is consistent across app and package metadata', () => {
  const app = JSON.parse(read('mobile/app.json')).expo;
  const pkg = JSON.parse(read('mobile/package.json'));
  const lock = JSON.parse(read('mobile/package-lock.json'));
  assert.equal(app.name, 'CueBell');
  assert.equal(app.slug, 'cuebell');
  assert.equal(app.scheme, 'cuebell');
  assert.equal(app.android.package, 'app.cuebell.mobile');
  assert.equal(app.version, '1.3.0');
  assert.equal(app.android.versionCode, 5);
  assert.equal(pkg.name, 'cuebell-mobile');
  assert.equal(pkg.version, app.version);
  assert.equal(lock.name, pkg.name);
  assert.equal(lock.version, pkg.version);
  assert.equal(lock.packages[''].name, pkg.name);
  assert.equal(lock.packages[''].version, pkg.version);
  assert.match(read('backend/pyproject.toml'), /^name = "cuebell"$/m);
  assert.match(read('backend/app/main.py'), /FastAPI\(title="CueBell relay"/);
});

test('release profiles use the current backend and preserve native alert identity', () => {
  const profiles = JSON.parse(read('mobile/eas.json')).build;
  for (const profile of ['preview', 'production']) {
    assert.equal(profiles[profile].env.EXPO_PUBLIC_API_URL, origin);
  }
  assert.match(read('mobile/.env.example'), new RegExp(`^EXPO_PUBLIC_API_URL=${origin.replaceAll('.', '\\.')}$`, 'm'));
  assert.match(read('mobile/src/app/index.tsx'), />CueBell<\/Text>/);
  assert.match(read('mobile/src/lib/api.ts'), /'cuebell\.connection\.v1'/);
  const native = read('mobile/modules/queue-listener/android/src/main/java/expo/modules/queuelistener/ListenerService.kt');
  assert.match(native, /"CueBell · monitoring"/);
  assert.match(native, /"CueBell alert"/);
  assert.match(native, /"CueBell:Listening"/);
});

test('tracked application source contains no legacy product name or backend origin', () => {
  const files = execFileSync('git', ['ls-files', '-z'], { cwd: root, encoding: 'utf8' }).split('\0').filter(Boolean);
  const legacy = new RegExp('queue' + 'saathi', 'i');
  for (const name of files) {
    // Operations retain the installed server's service name and environment path.
    if (name.startsWith('ops/')) continue;
    if (!existsSync(new URL(`../../${name}`, import.meta.url))) continue;
    const bytes = readFileSync(new URL(`../../${name}`, import.meta.url));
    if (bytes.includes(0)) continue;
    const text = bytes.toString('utf8');
    assert.equal(legacy.test(text), false, `Legacy branding in ${name}`);
  }
});
