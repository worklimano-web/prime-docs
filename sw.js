/* PRIME DOCS — KILL-SWITCH service worker (R16 зам.: офлайн ОТКЛЮЧЁН по решению владельца).
   Прежний SW делал офлайн-precache оболочки (cache-first) и держал закэшированную обёртку с кнопкой «📴 Офлайн».
   Этот SW НИЧЕГО не кэширует и НИЧЕГО не перехватывает: при активации чистит ВСЕ старые кэши и САМ разрегистрируется,
   затем перезагружает открытые вкладки — так свежая обёртка (без офлайна) встаёт надёжно, а не через 2-3 захода.
   Браузер сверяет sw.js с сетью на каждой навигации: этот файл отличается от pd-shell-v2 → ставится вместо него.
   Вернуть офлайн (если понадобится) — восстановить прежний sw.js из git-истории и регистрацию в index.html. */
self.addEventListener('install', function () { self.skipWaiting(); });

self.addEventListener('activate', function (e) {
  e.waitUntil(
    caches.keys()
      .then(function (keys) { return Promise.all(keys.map(function (k) { return caches.delete(k); })); })   // снести весь офлайн-кэш
      .then(function () { return self.registration.unregister(); })                                          // снять сам SW
      .then(function () { return self.clients.matchAll({ type: 'window' }); })
      .then(function (clients) { clients.forEach(function (c) { try { c.navigate(c.url); } catch (e2) {} }); })   // перезагрузить вкладки → свежая обёртка
      .catch(function () {})
  );
});

/* fetch НЕ перехватываем — все запросы идут в сеть как обычно (офлайна больше нет). */
