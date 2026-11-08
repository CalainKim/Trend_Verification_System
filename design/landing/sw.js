// TrendCheck 서비스 워커. 홈 화면에 설치한 앱이 빨리 뜨고, 연결이 끊겨도
// 마지막으로 본 화면을 보여 주게 한다.
//
// 지키는 것
//   /api/, /auth/   절대 가로채지 않는다. 로그인과 심층 검증은 항상 서버로 간다
//   영상(mp4)       담지 않는다. 크고 부분 요청(range)을 쓴다
//   리디렉션         담지 않는다. 로그인 전 /app/ 은 /login 으로 가는 응답이라
//                   담아 두면 로그인한 뒤에도 입력 창이 뜬다
//   로그아웃         담아 둔 /app/ 을 지운다. 이 기기에 모니터 화면이 남지 않게

const VERSION = 'tc-2026-11-08b';
const PRECACHE = [
  // Pages 는 /offline.html 을 /offline 으로 돌려보낸다(308). 돌려보낸 응답을 담으면
  // 화면 요청에 쓸 수 없어서 처음부터 /offline 을 담는다
  '/offline',
  // 랜딩은 처음 설치할 때 담는다. 서비스 워커는 처음 열린 화면에는 끼어들지 못한다
  '/',
  '/assets/pwa/icon-192.png',
  '/assets/musinsa-logo.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(VERSION).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

const cacheable = (res) => res && res.ok && res.type === 'basic' && !res.redirected;

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname === '/auth/logout') {
    event.respondWith(
      caches.open(VERSION)
        .then((c) => c.keys().then((ks) => Promise.all(ks.filter((k) => new URL(k.url).pathname.startsWith('/app')).map((k) => c.delete(k)))))
        .then(() => fetch(req))
    );
    return;
  }
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/auth/')) return;
  if (url.pathname.endsWith('.mp4')) return;

  // 화면: 먼저 서버에 묻고, 끊겼으면 마지막으로 본 화면이나 오프라인 안내
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (cacheable(res)) {
            const copy = res.clone();
            caches.open(VERSION).then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(async () => (await caches.match(req)) || caches.match('/offline'))
    );
    return;
  }

  // 그림, 글꼴, 아이콘: 담아 둔 것을 바로 쓰고 뒤에서 새로 받아 둔다
  if (url.pathname.startsWith('/assets/')) {
    event.respondWith(
      caches.open(VERSION).then(async (c) => {
        const hit = await c.match(req);
        const fresh = fetch(req).then((res) => { if (cacheable(res)) c.put(req, res.clone()); return res; }).catch(() => hit);
        return hit || fresh;
      })
    );
  }
});
