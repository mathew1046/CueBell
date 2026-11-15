import assert from 'node:assert/strict';
import test from 'node:test';

let instance = 0;
const freshAdapter = () => import(`../src/lib/storage.web.ts?test=${instance++}`);

function browser(t, value) {
  const original = Object.getOwnPropertyDescriptor(globalThis, 'window');
  Object.defineProperty(globalThis, 'window', { configurable: true, value });
  t.after(() => {
    if (original) Object.defineProperty(globalThis, 'window', original);
    else delete globalThis.window;
  });
}

function stored(values = new Map()) {
  return { getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) };
}

test('browser credentials and preferences retain their distinct persistence scopes', async t => {
  const session = new Map(), local = new Map();
  browser(t, { sessionStorage: stored(session), localStorage: stored(local) });
  const storage = await freshAdapter();
  await storage.setItemAsync('cuebell.connection.v1', 'bearer');
  await storage.setItemAsync('cuebell.theme.v1', 'dark');
  assert.equal(session.get('cuebell.connection.v1'), 'bearer');
  assert.equal(local.get('cuebell.theme.v1'), 'dark');
  assert.equal(session.has('cuebell.theme.v1'), false);
});

test('blocked storage properties leave a usable page-local session', async t => {
  const blocked = {};
  for (const name of ['sessionStorage', 'localStorage']) {
    Object.defineProperty(blocked, name, { get() { throw new DOMException('Blocked', 'SecurityError'); } });
  }
  browser(t, blocked);
  const storage = await freshAdapter();
  assert.equal(await storage.getItemAsync('cuebell.connection.v1'), null);
  await storage.setItemAsync('cuebell.connection.v1', 'bearer');
  await storage.setItemAsync('cuebell.language.v1', 'ml');
  assert.equal(await storage.getItemAsync('cuebell.connection.v1'), 'bearer');
  assert.equal(await storage.getItemAsync('cuebell.language.v1'), 'ml');
  await storage.deleteItemAsync('cuebell.connection.v1');
  assert.equal(await storage.getItemAsync('cuebell.connection.v1'), null);
  assert.equal(await (await freshAdapter()).getItemAsync('cuebell.language.v1'), null);
});

test('failed writes and deletes cannot resurrect a readable stale credential in the current page', async t => {
  const values = new Map([['cuebell.connection.v1', 'old bearer']]);
  const quota = { ...stored(values),
    setItem() { throw new DOMException('Full', 'QuotaExceededError'); },
    removeItem() { throw new DOMException('Blocked', 'SecurityError'); } };
  browser(t, { sessionStorage: quota });
  const storage = await freshAdapter();
  assert.equal(await storage.getItemAsync('cuebell.connection.v1'), 'old bearer');
  await storage.setItemAsync('cuebell.connection.v1', 'replacement');
  assert.equal(await storage.getItemAsync('cuebell.connection.v1'), 'replacement');
  await storage.deleteItemAsync('cuebell.connection.v1');
  assert.equal(await storage.getItemAsync('cuebell.connection.v1'), null);
  assert.equal(values.get('cuebell.connection.v1'), 'old bearer');
});

test('server rendering neither accesses browser storage nor retains request data', async t => {
  browser(t, undefined);
  const storage = await freshAdapter();
  await storage.setItemAsync('cuebell.connection.v1', 'server value');
  await storage.deleteItemAsync('cuebell.theme.v1');
  assert.equal(await storage.getItemAsync('cuebell.connection.v1'), null);
  Object.defineProperty(globalThis, 'window', { configurable: true, value: { sessionStorage: stored() } });
  assert.equal(await storage.getItemAsync('cuebell.connection.v1'), null);
});
