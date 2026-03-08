const CACHE_NAME = "news-digest-v4";

// Static assets to cache for offline shell
const STATIC_ASSETS = [
  "/",
  "/style.css",
  "/script.js",
  "/manifest.json",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
];

// ── Install: cache static shell ───────────────────────────────────────────────
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

// ── Activate: clean up old caches ─────────────────────────────────────────────
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// ── Fetch: serve shell from cache, API calls always go to network ─────────────
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // SSE streams MUST bypass the service worker entirely — wrapping them in
  // respondWith(fetch()) causes buffering in some browsers which breaks streaming.
  if (url.pathname.includes("/stream")) {
    return; // let the browser handle SSE directly, no respondWith
  }

  // Always fetch other API calls from the network (live data)
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(event.request).catch(() =>
        new Response(
          JSON.stringify({ error: "You are offline. Please connect to the internet." }),
          { headers: { "Content-Type": "application/json" } }
        )
      )
    );
    return;
  }

  // Serve static assets from cache, fall back to network
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});
