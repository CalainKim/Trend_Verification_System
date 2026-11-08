// 로그아웃. 쿠키를 지우고 랜딩으로 보낸다.

import { clearCookie } from '../_shared/session.js';

export function onRequest() {
  return new Response(null, {
    status: 303,
    headers: { location: '/', 'set-cookie': clearCookie(), 'cache-control': 'no-store' },
  });
}
