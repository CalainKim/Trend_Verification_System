// 비밀번호 게이트 검사. node web/functions/auth.test.mjs
import { onRequest as gate } from './_middleware.js';
import { onRequestPost as login } from './auth/login.js';
import { onRequest as logout } from './auth/logout.js';
import { issueCookie, hasSession, safeNext } from './_shared/session.js';

const env = { SITE_PASSWORD: 'correct horse battery', SESSION_SECRET: 'test-secret-0123456789', FAIL_DELAY_MS: 0 };
const NEXT_OK = new Response('next called', { status: 200 });

const callGate = (path, cookie, e = env) => gate({
  request: new Request('https://tc.example' + path, { headers: cookie ? { cookie } : {} }),
  env: e, next: async () => NEXT_OK.clone(),
});
const postLogin = (body, e = env) => login({
  request: new Request('https://tc.example/auth/login', {
    method: 'POST', body: new URLSearchParams(body).toString(),
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
  }), env: e,
});
const cookieOf = (res) => (res.headers.get('set-cookie') || '').split(';')[0];

let pass = 0, fail = 0;
const t = async (label, run, want) => {
  let got; try { got = await run(); } catch (err) { got = 'ERR ' + err.message; }
  const ok = got === want; ok ? pass++ : fail++;
  console.log(`  ${ok ? 'O' : 'X'}  ${label.padEnd(46)} ${got}${ok ? '' : '   기대 ' + want}`);
};

console.log('=== 공개 경로는 그대로 지난다 ===');
await t('랜딩 / 는 통과', async () => (await callGate('/')).status, 200);
await t('입력 창 /login 은 통과', async () => (await callGate('/login')).status, 200);
await t('랜딩 자산은 통과', async () => (await callGate('/assets/hero/s1_collect.mp4')).status, 200);
await t('/application 처럼 앞만 같은 경로는 통과', async () => (await callGate('/application')).status, 200);

console.log('\n=== 로그인 없이 막는다 ===');
await t('/app/ 은 입력 창으로 302', async () => (await callGate('/app/')).status, 302);
await t('돌아갈 곳을 붙여 보낸다', async () => (await callGate('/app/?tab=x')).headers.get('location'),
  'https://tc.example/login?next=%2Fapp%2F%3Ftab%3Dx');
await t('/app 도 막는다', async () => (await callGate('/app')).status, 302);
await t('/api/complete 는 401', async () => (await callGate('/api/complete')).status, 401);
await t('비밀값이 없으면 열지 않고 500', async () => (await callGate('/app/', null, {})).status, 500);

console.log('\n=== 비밀번호 확인 ===');
await t('틀린 비밀번호는 입력 창으로 되돌린다', async () => (await postLogin({ password: 'nope', next: '/app/' })).headers.get('location'),
  '/login?e=1&next=%2Fapp%2F');
await t('틀리면 쿠키를 주지 않는다', async () => cookieOf(await postLogin({ password: 'nope' })), '');
await t('빈 비밀번호도 거절', async () => cookieOf(await postLogin({ password: '' })), '');
await t('맞으면 303 으로 원래 가려던 곳', async () => {
  const r = await postLogin({ password: env.SITE_PASSWORD, next: '/app/?tab=x' });
  return r.status + ' ' + r.headers.get('location');
}, '303 /app/?tab=x');
await t('쿠키는 HttpOnly, Secure, SameSite', async () => {
  const c = (await postLogin({ password: env.SITE_PASSWORD })).headers.get('set-cookie');
  return ['HttpOnly', 'Secure', 'SameSite=Lax', 'Max-Age=604800'].every((k) => c.includes(k));
}, true);
await t('바깥 주소로 내보내지 않는다 //evil.com', async () => (await postLogin({ password: env.SITE_PASSWORD, next: '//evil.com' })).headers.get('location'), '/app/');
await t('바깥 주소로 내보내지 않는다 https://', async () => safeNext('https://evil.com'), '/app/');
await t('역슬래시 우회도 막는다', async () => safeNext('/\\evil.com'), '/app/');

console.log('\n=== 로그인 쿠키 ===');
const good = cookieOf(await postLogin({ password: env.SITE_PASSWORD }));
await t('쿠키가 있으면 /app/ 통과', async () => (await callGate('/app/', good)).status, 200);
await t('통과한 화면은 캐시에 남기지 않는다', async () => (await callGate('/app/', good)).headers.get('cache-control'), 'private, no-store');
await t('쿠키가 있으면 /api 통과', async () => (await callGate('/api/complete', good)).status, 200);
await t('서명을 바꾼 쿠키는 막는다', async () => (await callGate('/app/', good.slice(0, -2) + 'xx')).status, 302);
await t('만료 시각을 늘린 쿠키는 막는다', async () => {
  const [name, v] = good.split('='); const [exp, sig] = v.split('.');
  return (await callGate('/app/', `${name}=${Number(exp) + 999999}.${sig}`)).status;
}, 302);
await t('다른 비밀값으로 만든 쿠키는 막는다', async () => {
  const forged = (await issueCookie({ ...env, SESSION_SECRET: 'other' })).split(';')[0];
  return (await callGate('/app/', forged)).status;
}, 302);
await t('만료된 쿠키는 막는다', async () => {
  const old = (await issueCookie(env, Date.now() - 8 * 24 * 3600 * 1000)).split(';')[0];
  return (await callGate('/app/', old)).status;
}, 302);
await t('비밀번호를 바꾸면 이전 쿠키는 무효', async () => (await callGate('/app/', good, { ...env, SITE_PASSWORD: 'new pass' })).status, 302);
await t('다른 쿠키 사이에 있어도 읽는다', async () => hasSession(new Request('https://x/', { headers: { cookie: 'a=1; ' + good + '; b=2' } }), env), true);

console.log('\n=== 로그아웃 ===');
await t('쿠키를 지우고 랜딩으로', async () => {
  const r = logout(); return r.headers.get('location') + ' ' + r.headers.get('set-cookie').includes('Max-Age=0');
}, '/ true');

console.log(`\n통과 ${pass}  실패 ${fail}`);
if (fail) process.exit(1);
