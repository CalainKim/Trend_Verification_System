// 비밀번호 게이트. 모든 요청이 여기를 먼저 지난다.
//
//   /           랜딩. 누구나
//   /login      비밀번호 입력 창. 누구나
//   /app/...    모니터. 로그인한 사람만. 아니면 입력 창으로 보낸다
//   /api/...    중계. 로그인한 사람만. 아니면 401
//
// 화면 쪽 스크립트로 막지 않고 여기서 막는 이유는, 화면에서 막으면 소스를
// 보거나 주소를 직접 쳐서 넘어갈 수 있기 때문이다. 특히 /api 는 API 키로
// 돈이 드는 호출이라 서버에서 거르지 않으면 주소만 알면 누구나 부를 수 있다.

import { configured, hasSession, safeNext } from './_shared/session.js';

const GATED = [/^\/app(\/|$)/, /^\/api(\/|$)/];

export async function onRequest(ctx) {
  const { request, env, next } = ctx;
  const url = new URL(request.url);
  if (!GATED.some((re) => re.test(url.pathname))) return next();

  // 비밀값을 빠뜨리고 배포하면 열어 두지 않고 닫아 둔다
  if (!configured(env)) {
    return new Response('서버에 SITE_PASSWORD 와 SESSION_SECRET 이 설정되지 않았습니다.', {
      status: 500, headers: { 'content-type': 'text/plain; charset=utf-8' },
    });
  }

  if (await hasSession(request, env)) {
    const res = await next();
    // 로그인한 화면이 검색엔진이나 공용 캐시에 남지 않게
    const out = new Response(res.body, res);
    out.headers.set('cache-control', 'private, no-store');
    out.headers.set('x-robots-tag', 'noindex');
    return out;
  }

  if (url.pathname.startsWith('/api')) {
    return new Response(JSON.stringify({ error: { message: '로그인이 필요합니다.' } }), {
      status: 401, headers: { 'content-type': 'application/json; charset=utf-8' },
    });
  }
  const back = safeNext(url.pathname + url.search);
  return Response.redirect(new URL('/login?next=' + encodeURIComponent(back), url).toString(), 302);
}
