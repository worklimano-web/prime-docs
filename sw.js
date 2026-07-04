/* PRIME DOCS — минимальный service worker.
   Нужен только для «устанавливаемости» (Chrome требует SW c fetch-обработчиком).
   Ничего не кэшируем: приложение живёт во вложенном iframe (script.google.com),
   поэтому просто пропускаем запросы как есть. */
self.addEventListener('install', function (e) { self.skipWaiting(); });
self.addEventListener('activate', function (e) { e.waitUntil(self.clients.claim()); });
self.addEventListener('fetch', function (e) { /* passthrough */ });
