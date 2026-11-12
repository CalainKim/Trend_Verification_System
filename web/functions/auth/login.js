// 비밀번호 입력 창이 보내는 곳. 맞으면 로그인 쿠키를 주고 원래 가려던 곳으로 보낸다.
//
// 틀리면 응답을 늦춘다. 무료 등급에서는 호출 횟수 제한을 따로 걸기 어려워서,
// 한 번 틀릴 때마다 시간을 들게 해 자동 대입을 느리게 만든다. 그래서
// 비밀번호는 짧은 단어보다 길게 정하는 것이 맞다.

import { checkPassword, configured, issueCookie, safeNext } from '../_shared/session.js';

const FAIL_DELAY_MS = 600;
const MAX_BODY = 4 * 1024;

// 다른 주소로 보내는 응답을 만든다. 쿠키를 함께 심을 수 있다.
const go = (location, cookie) => {
  const headers = new Headers({ location, 'cache-control': 'no-store' });
  if (cookie) headers.append('set-cookie', cookie);
  return new Response(null, { status: 303, headers });
};

// 비밀번호를 받아 맞으면 입장권 쿠키를 주고 원래 가려던 곳으로 보낸다. 틀리면 잠깐 기다린 뒤 되돌린다.
export async function onRequestPost({ request, env }) {
  if (!configured(env)) {
    return new Response('서버에 SITE_PASSWORD 와 SESSION_SECRET 이 설정되지 않았습니다.', {
      status: 500, headers: { 'content-type': 'text/plain; charset=utf-8' },
    });
  }
  const raw = await request.text();
  if (raw.length > MAX_BODY) return new Response('요청이 너무 큽니다.', { status: 413 });
  const form = new URLSearchParams(raw);
  const next = safeNext(form.get('next'));

  if (await checkPassword(form.get('password') || '', env)) {
    return go(next, await issueCookie(env));
  }
  await new Promise((r) => setTimeout(r, env.FAIL_DELAY_MS === undefined ? FAIL_DELAY_MS : Number(env.FAIL_DELAY_MS)));
  return go('/login?e=1&next=' + encodeURIComponent(next));
}

// 주소창으로 직접 들어오면 입력 창으로 돌려보낸다
export function onRequestGet() {
  return go('/login');
}
