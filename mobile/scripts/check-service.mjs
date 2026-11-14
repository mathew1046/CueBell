import { loadEnvFile } from 'node:process';
try { loadEnvFile('.env'); } catch (error) { if (error.code !== 'ENOENT') throw error; }
const value = process.env.EXPO_PUBLIC_API_URL;
let valid = false;
try {
  const url = new URL(value);
  const local = process.env.EXPO_PUBLIC_ALLOW_INSECURE_LOCAL === 'true' && url.protocol === 'http:' &&
    ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
  const deployed = url.protocol === 'https:' && !/\.(example|invalid|test)$/.test(url.hostname) && url.hostname !== 'localhost';
  valid = (deployed || local) && !url.username && !url.password && !url.search && !url.hash && url.pathname === '/';
} catch { /* A missing or malformed operator setting must not ship silently. */ }
if (!valid) {
  console.error('Set EXPO_PUBLIC_API_URL to the deployed HTTPS backend origin, or explicitly allow loopback HTTP with EXPO_PUBLIC_ALLOW_INSECURE_LOCAL=true. Do not add API keys or pairing secrets.');
  process.exit(1);
}
console.log('Build-time service origin validated.');
