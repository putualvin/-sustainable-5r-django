const CACHE = '5r-shell-v1';
const SHELL = ['/offline/', '/static/app.css', '/static/offline.js', '/static/icon.svg'];
self.addEventListener('install', event => {event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL)));self.skipWaiting();});
self.addEventListener('activate', event => event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith('5r-shell-') && k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if(event.request.method !== 'GET' || url.origin !== self.location.origin) return;
  if(SHELL.includes(url.pathname)) {
    event.respondWith(fetch(event.request).then(response => {if(response.ok) {const copy=response.clone();caches.open(CACHE).then(cache=>cache.put(url.pathname, copy));}return response;}).catch(()=>caches.match(url.pathname)));
  } else if(event.request.mode === 'navigate') {
    // Never cache authenticated HTML or evidence. Offline content lives in a user-scoped IndexedDB store.
    event.respondWith(fetch(event.request).catch(()=>caches.match('/offline/')));
  }
});
