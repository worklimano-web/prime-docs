/* PRIME DOCS — service worker с офлайн-precache ОБОЛОЧКИ.
   Было (аддитивно расширяем): passthrough без кэша — только чтобы PWA была «устанавливаемой».
   Стало: кэшируем САМУ обёртку (shell), офлайн-доску offline.html и шрифты бренда + иконочный
   Material Symbols → приложение открывается БЕЗ сети (стратегия cache-first).
   ⚠ Приложение живёт во вложенном iframe script.google.com — эти запросы НЕ трогаем (идут в сеть,
   как раньше). Кэшируем только СВОЙ origin (github.io) и хосты Google Fonts. */
var CACHE = 'pd-shell-v2';                                  // ← поднимать при изменении precache-списка
var SHELL = [
  './', 'index.html', 'offline.html', 'manifest.json',
  'icon-192.png', 'icon-512.png'
];
/* CSS Google Fonts UA-зависим (отдаёт разные @font-face под браузер), поэтому тянем его В SW (тот же UA),
   парсим ссылки на woff2 и кэшируем И css, И файлы — иначе значки/шрифты офлайн бы не встали.
   Оба URL — дословно те, что грузят offline.html (@import с Material Symbols) и index.html (<link>, текст). */
var FONT_CSS = [
  'https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0&display=swap',
  'https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap'
];

/* Best-effort: тянем CSS как CORS (googleapis отдаёт CORS-заголовки → ответ читаемый, годится и как
   стиль для no-cors @import), из него достаём woff2 (gstatic) и кэшируем. Ошибки глотаем — установка
   не должна падать из-за шрифтов/офлайн-инсталла. */
function precacheFonts(cache) {
  return Promise.all(FONT_CSS.map(function (url) {
    return fetch(url, { mode: 'cors' }).then(function (res) {
      if (!res || !res.ok) return;
      return cache.put(url, res.clone()).then(function () {
        return res.text();
      }).then(function (css) {
        var files = css.match(/https:\/\/fonts\.gstatic\.com\/[^)'"]+/g) || [];
        return Promise.all(files.map(function (f) {
          return fetch(f, { mode: 'cors' }).then(function (fr) {
            if (fr && fr.ok) return cache.put(f, fr.clone());
          }).catch(function () {});
        }));
      });
    }).catch(function () {});
  }));
}

self.addEventListener('install', function (e) {
  e.waitUntil(
    caches.open(CACHE).then(function (cache) {
      // shell — по одному (addAll падает целиком, если хоть один файл не отдался); шрифты — best-effort
      return Promise.all(SHELL.map(function (u) {
        return cache.add(u).catch(function () {});
      })).then(function () {
        return precacheFonts(cache);
      });
    }).then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.map(function (k) {
        return k === CACHE ? null : caches.delete(k);       // старое чистим
      }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') return;                          // POST и пр. — как раньше (passthrough)
  var url;
  try { url = new URL(req.url); } catch (err) { return; }
  var isFont = (url.host === 'fonts.googleapis.com' || url.host === 'fonts.gstatic.com');
  var isShell = (url.origin === self.location.origin);
  if (!isFont && !isShell) return;                           // приложение (script.google.com и др.) — сеть как есть

  // stale-while-revalidate: если есть в кэше — отдаём мгновенно (и офлайн), а в фоне обновляем; если нет —
  // идём в сеть и КЛАДЁМ В КЭШ (так шрифт ложится в кэш при ПЕРВОМ онлайн-открытии, даже если precache не успел).
  e.respondWith(
    caches.open(CACHE).then(function (cache) {
      return cache.match(req).then(function (cached) {
        // CSS Google Fonts тянем как CORS (читаемый ответ, годный и как стиль для no-cors @import).
        var netReq = (url.host === 'fonts.googleapis.com') ? new Request(req.url, { mode: 'cors' }) : req;
        var network = fetch(netReq).then(function (res) {
          if (res && (res.ok || res.type === 'opaque')) { try { cache.put(req, res.clone()); } catch (e2) {} }
          return res;
        }).catch(function () { return null; });
        if (cached) return cached;                          // кэш сразу; обновление (network) уже в полёте
        return network.then(function (res) {
          if (res) return res;
          // офлайн и нет в кэше: навигацию отдаём оболочкой (её точка входа — index.html)
          if (req.mode === 'navigate') { return cache.match('index.html').then(function (idx) { return idx || cache.match('./'); }); }
          return Response.error();
        });
      });
    })
  );
});
