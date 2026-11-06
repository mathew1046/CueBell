import { loadEnvFile } from 'node:process';
try { loadEnvFile('.env'); } catch (error) { if (error.code !== 'ENOENT') throw error; }
const value = process.env.EXPO_PUBLIC_API_URL;
let valid = false;
try {
  const url = new URL(value);
  valid = url.protocol === 'https:' && !url.username && !url.password && !url.search && !url.hash &&
    url.pathname === '/' && !/\.(example|invalid|test)$/.test(url.hostname) && url.hostname !== 'localhost';
} catch { /* A missing or malformed operator setting must not ship silently. */ }
if (!valid) {
  console.error('Set EXPO_PUBLIC_API_URL to the deployed HTTPS backend origin before building. Do not add API keys or pairing secrets.');
  process.exit(1);
}
console.log('Build-time service origin validated.');
