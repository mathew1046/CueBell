// Notifications only. Audio, bearer credentials and transcripts are never cached.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil((async () => {
    let destination;
    try { destination = new URL(event.notification.data?.url || '/', self.location.origin); }
    catch { destination = new URL('/', self.location.origin); }
    if (destination.origin !== self.location.origin) destination = new URL('/', self.location.origin);
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    const window = windows.find(client => client.url === destination.href) ??
      windows.find(client => new URL(client.url).origin === self.location.origin);
    if (window) await window.focus();
    else await self.clients.openWindow(destination.href);
  })());
});
