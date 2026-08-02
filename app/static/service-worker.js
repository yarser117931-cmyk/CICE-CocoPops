
const CACHE_NAME = "cice-v11-0-0";
const STATIC_ASSETS = [
  "/static/manifest.webmanifest?v=11.0.0",
  "/static/icon-192.png?v=11.0.0",
  "/static/icon-512.png?v=11.0.0",
  "/static/apple-touch-icon.png?v=11.0.0",
  "/static/cocopops-logo.png?v=11.0.0",
  "/static/cocopops-fashion-mall-hero.jpg?v=11.0.0"
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", event => {
  const request = event.request;
  const url = new URL(request.url);

  if (request.method !== "GET") return;

  // Never cache live Odoo-backed data.
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(fetch(request, {cache: "no-store"}));
    return;
  }

  // Always try the newest HTML first, so updates appear on phone and PC.
  if (request.mode === "navigate" || url.pathname === "/") {
    event.respondWith(
      fetch(request, {cache: "no-store"})
        .then(response => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put("/", copy));
          return response;
        })
        .catch(() => caches.match("/"))
    );
    return;
  }

  // Static files: cache first, then network.
  event.respondWith(
    caches.match(request).then(cached =>
      cached || fetch(request).then(response => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(request, copy));
        return response;
      })
    )
  );
});
