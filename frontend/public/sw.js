const CACHE_NAME = 'autodrive-cache-v3';

self.addEventListener('install', (event) => {
  // Ativa o novo Service Worker imediatamente sem esperar fechar as abas
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cache) => {
          if (cache !== CACHE_NAME) {
            console.log('[SW] Apagando cache antigo:', cache);
            return caches.delete(cache);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = event.request.url;

  // Ignora requisições que não sejam GET, chamadas de API ou servidores de backend/mídia
  if (
    event.request.method !== 'GET' ||
    url.includes('/api/') ||
    url.includes('onrender.com') ||
    url.includes('cloudinary.com') ||
    url.includes('supabase.co') ||
    url.includes('supabase.com')
  ) {
    return;
  }

  // Network-First para navegação (HTML) para nunca travar o usuário em builds antigos
  if (event.request.mode === 'navigate' || event.request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          if (response && response.status === 200) {
            const cacheCopy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, cacheCopy));
          }
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // Cache First com Network Fallback para assets estáticos
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }
      return fetch(event.request).then((response) => {
        if (response && response.status === 200 && event.request.url.startsWith(self.location.origin)) {
          const cacheCopy = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, cacheCopy);
          });
        }
        return response;
      });
    })
  );
});
