// SivarCasas Service Worker — Minimal & Conservative
// Only caches static assets. NEVER caches API responses or dynamic data.

const CACHE_NAME = 'sivarcasas-v1';

// Assets to pre-cache during install (app shell)
const PRECACHE_URLS = [
  '/offline.html',
];

// ─── Install: pre-cache offline fallback ────────────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS))
  );
  // Activate immediately without waiting for existing clients to close
  self.skipWaiting();
});

// ─── Activate: clean old caches ─────────────────────────────────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      )
    )
  );
  // Take control of all open tabs immediately
  self.clients.claim();
});

// ─── Fetch: route-based strategy ────────────────────────────────────
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // 1. Skip non-GET requests (POST to /api/valuador, etc.)
  if (request.method !== 'GET') return;

  // 2. NEVER cache API routes — always go to network
  if (url.pathname.startsWith('/api/')) return;

  // 3. NEVER cache map tiles (OSM, etc.)
  if (
    url.hostname.includes('tile.openstreetmap.org') ||
    url.hostname.includes('tiles') ||
    url.hostname.includes('nominatim')
  ) {
    return;
  }

  // 4. Static assets (/_next/static/*, icons, fonts) → Cache-first
  if (
    url.pathname.startsWith('/_next/static/') ||
    url.pathname.startsWith('/icons/') ||
    url.hostname === 'fonts.googleapis.com' ||
    url.hostname === 'fonts.gstatic.com'
  ) {
    event.respondWith(
      caches.match(request).then((cached) => {
        if (cached) return cached;
        return fetch(request).then((response) => {
          // Only cache successful responses
          if (!response || response.status !== 200) return response;
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          return response;
        });
      })
    );
    return;
  }

  // 5. Navigation requests → Network-first with offline fallback
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(() => caches.match('/offline.html'))
    );
    return;
  }

  // 6. Everything else → Network only (no caching)
  // This intentionally falls through so the browser handles normally.
});
