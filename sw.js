/* PRIME DOCS — МИНИМАЛЬНЫЙ service worker: ТОЛЬКО приём файла из системного «Поделиться».
   (R17 D543, решение владельца: «поделиться напрямую в PRIME DOCS, без единой строчки офлайна».)

   Почему он вообще нужен. Android показывает приложение в списке «Поделиться» только если у него
   объявлен share_target в манифесте. Телефон при этом шлёт POST с файлом, а страница на GitHub Pages
   POST принять не может — статический хостинг. Перехватить POST способен только service worker.

   Что он НЕ делает (и не должен): ничего не кэширует, GET-запросы не перехватывает, офлайн-оболочку
   не поднимает. Офлайн владелец выключил осознанно — прежний kill-switch SW чистил кэши и снимал
   сам себя. Здесь наследие офлайна тоже сносится: при активации удаляем ВСЕ кэши, кроме своего
   кармана для шара. Отличие от kill-switch одно: этот SW остаётся жить, иначе принимать «Поделиться»
   будет нечем.

   Дальнейший путь файла: положили в кэш → увели страницу на ./?shared=1 → обёртка (index.html) читает
   карман, переводит файл в base64 и шлёт приложению сообщением pdshared → приложение кладёт файл
   на Диск и заводит запись во «Входящих». Обе стороны этой цепочки уже написаны (D523). */

var SHARE_CACHE = 'pd-share';

self.addEventListener('install', function () { self.skipWaiting(); });

self.addEventListener('activate', function (e) {
  e.waitUntil(
    caches.keys()
      .then(function (keys) {
        return Promise.all(keys.map(function (k) {
          return k === SHARE_CACHE ? null : caches.delete(k);   // офлайн-наследие сносим, карман шара оставляем
        }));
      })
      .then(function () { return self.clients.claim(); })
      .catch(function () {})
  );
});

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'POST') return;                            // всё остальное — в сеть как обычно, мы не вмешиваемся
  var u;
  try { u = new URL(req.url); } catch (err) { return; }
  if (u.origin !== self.location.origin || !/\/share\/?$/.test(u.pathname)) return;

  e.respondWith((function () {
    return req.formData().then(function (fd) {
      var f = fd.get('file');
      var meta = { text: String(fd.get('text') || fd.get('title') || ''), at: Date.now(), file: 0, name: '', mime: '' };
      return caches.open(SHARE_CACHE).then(function (c) {
        var put = Promise.resolve();
        if (f && f.size) {
          meta.file = 1;
          meta.name = f.name || 'scan.pdf';
          meta.mime = f.type || 'application/pdf';
          put = c.put('shared-file', new Response(f));
        }
        return put.then(function () {
          return c.put('shared-meta', new Response(JSON.stringify(meta), { headers: { 'content-type': 'application/json' } }));
        });
      });
    }).then(function () {
      return Response.redirect('./?shared=1', 303);
    }).catch(function () {
      return Response.redirect('./?shared=err', 303);
    });
  })());
});
