/* The hub's own service worker.
 *
 * The page argues that nothing here needs the network. Until this file existed
 * that was only true of the projects it lists — the hub itself showed a
 * browser error page the moment you came back without a signal. Now the shell,
 * the project data and every thumbnail you have already seen survive a dead
 * connection, and the site is installable to a phone home screen.
 *
 * Two rules, and they matter:
 *   1. The HTML is NETWORK-FIRST. Cache-first HTML is how a shipped release
 *      becomes invisible — a returning reader keeps the old page and has no
 *      way to know. Network wins, the cache is only the fallback.
 *   2. Bump CACHE on every release. An unchanged cache name is the same bug
 *      wearing a different hat.
 */

const CACHE = 'hub-2026-11-10-1';

const SHELL = [
  '/',
  '/index.html',
  '/assets/favicon.svg',
  '/assets/logo.svg',
  '/assets/site.webmanifest',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE)
      // One missing shell file must not fail the whole install.
      .then((cache) => Promise.allSettled(SHELL.map((u) => cache.add(u))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;   // never proxy another origin

  // Navigations: network first, cached page as the fallback.
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put('/index.html', copy)).catch(() => {});
          return res;
        })
        .catch(() =>
          caches.match('/index.html').then((hit) => hit || caches.match('/'))
        )
    );
    return;
  }

  // The project data: fresh when we can, stale when we cannot.
  if (url.pathname.endsWith('/repos.json')) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
          return res;
        })
        .catch(() => caches.match(req))
    );
    return;
  }

  // Everything else — thumbnails above all — cache first, then network.
  event.respondWith(
    caches.match(req).then((hit) => {
      if (hit) return hit;
      return fetch(req).then((res) => {
        if (res && res.status === 200 && res.type === 'basic') {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        }
        return res;
      });
    })
  );
});
