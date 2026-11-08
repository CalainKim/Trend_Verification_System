// 비밀번호 게이트가 함께 쓰는 로그인 쿠키 도구.
//
// 쿠키 값은 "만료시각.서명" 이다. 서명은 SESSION_SECRET 으로 만든 HMAC 이라
// 서버 밖에서는 만들 수 없다. 서명할 내용에 비밀번호의 해시를 섞어 두어서
// 비밀번호를 바꾸면 이전에 받은 쿠키가 모두 무효가 된다.
//
// 이 파일은 onRequest 를 내보내지 않으므로 경로가 되지 않는다.
//
// 환경변수
//   SITE_PASSWORD    필수. 들어올 사람에게 알려 주는 비밀번호
//   SESSION_SECRET   필수. 쿠키 서명용 임의 문자열. openssl rand -base64 32

export const COOKIE = 'tc_session';
export const MAX_AGE = 7 * 24 * 60 * 60; // 7일

const enc = new TextEncoder();

const b64url = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf)))
  .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');

async function hmac(secret, msg) {
  const key = await crypto.subtle.importKey('raw', enc.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return b64url(await crypto.subtle.sign('HMAC', key, enc.encode(msg)));
}

async function sha256(text) {
  return b64url(await crypto.subtle.digest('SHA-256', enc.encode(text)));
}

// 길이와 내용으로 일찍 끝나지 않게 끝까지 비교한다
function sameString(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string') return false;
  let diff = a.length ^ b.length;
  const n = Math.max(a.length, b.length);
  for (let i = 0; i < n; i++) diff |= (a.charCodeAt(i) || 0) ^ (b.charCodeAt(i) || 0);
  return diff === 0;
}

export function configured(env) {
  return Boolean(env && env.SITE_PASSWORD && env.SESSION_SECRET);
}

// 입력한 비밀번호가 맞는지. 두 값을 같은 키로 HMAC 한 뒤 비교해서
// 비교 시간이 비밀번호 내용에 따라 달라지지 않게 한다.
export async function checkPassword(input, env) {
  if (!configured(env) || typeof input !== 'string' || !input) return false;
  const [a, b] = await Promise.all([
    hmac(env.SESSION_SECRET, 'pw|' + input),
    hmac(env.SESSION_SECRET, 'pw|' + env.SITE_PASSWORD),
  ]);
  return sameString(a, b);
}

async function signedFor(exp, env) {
  return hmac(env.SESSION_SECRET, `v1|${exp}|${await sha256(env.SITE_PASSWORD)}`);
}

export async function issueCookie(env, now = Date.now()) {
  const exp = Math.floor(now / 1000) + MAX_AGE;
  const value = `${exp}.${await signedFor(exp, env)}`;
  return `${COOKIE}=${value}; Path=/; Max-Age=${MAX_AGE}; HttpOnly; Secure; SameSite=Lax`;
}

export function clearCookie() {
  return `${COOKIE}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax`;
}

function readCookie(header) {
  if (!header) return null;
  for (const part of header.split(';')) {
    const i = part.indexOf('=');
    if (i > 0 && part.slice(0, i).trim() === COOKIE) return part.slice(i + 1).trim();
  }
  return null;
}

export async function hasSession(request, env, now = Date.now()) {
  if (!configured(env)) return false;
  const value = readCookie(request.headers.get('cookie'));
  if (!value) return false;
  const dot = value.indexOf('.');
  if (dot < 1) return false;
  const exp = Number(value.slice(0, dot));
  if (!Number.isInteger(exp) || exp * 1000 <= now) return false;
  return sameString(value.slice(dot + 1), await signedFor(exp, env));
}

// 로그인 뒤 돌아갈 곳. 같은 사이트 안의 경로만 받는다.
// "//다른사이트" 나 "https://..." 로 밖으로 내보내는 길을 막는다.
export function safeNext(next) {
  if (typeof next !== 'string' || !next.startsWith('/') || next.startsWith('//') || next.includes('\\')) {
    return '/app/';
  }
  return next;
}
