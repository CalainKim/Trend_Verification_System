import { onRequestPost, onRequestGet } from './complete.js';

let sent = null;
globalThis.fetch = async (url, opts) => {
  sent = { url, body: JSON.parse(opts.body), headers: opts.headers };
  return new Response(JSON.stringify({
    content: [{ type: 'text', text: '{"verdict":"ok"}' }], stop_reason: 'end_turn',
  }), { status: 200, headers: { 'content-type': 'application/json' } });
};

const env = { ANTHROPIC_API_KEY: 'sk-ant-test-FAKE' };
const post = (body) => onRequestPost({
  request: new Request('https://x/api/complete', {
    method: 'POST', body: typeof body === 'string' ? body : JSON.stringify(body),
  }), env,
});

const good = { model: 'claude-sonnet-5-5', max_tokens: 2500,
               system: 'sys', messages: [{ role: 'user', content: 'hi' }] };
let pass = 0, fail = 0;
const t = async (label, run, want) => {
  const got = await run();
  const ok = got === want;
  ok ? pass++ : fail++;
  console.log(`  ${ok ? 'O' : 'X'}  ${label.padEnd(44)} ${got}${ok ? '' : '   기대 ' + want}`);
};

console.log('=== 정상 요청 ===');
await t('정상 요청은 200', async () => (await post(good)).status, 200);
console.log(`     모델         ${sent.body.model}`);
console.log(`     max_tokens   ${sent.body.max_tokens}`);
console.log(`     effort       ${sent.body.output_config.effort}`);
console.log(`     키 헤더 전달  ${sent.headers['x-api-key'] === env.ANTHROPIC_API_KEY}`);

console.log('\n=== 열린 중계 막기 ===');
await t('허용 목록에 없는 모델은 기본값으로', async () => {
  await post({ ...good, model: 'gpt-4o' }); return sent.body.model;
}, 'claude-sonnet-5-5');
await t('max_tokens 100000 은 상한으로', async () => {
  await post({ ...good, max_tokens: 100000 }); return sent.body.max_tokens;
}, 4000);
await t('이상한 effort 는 low 로', async () => {
  await post({ ...good, output_config: { effort: 'max' } });
  return sent.body.output_config.effort;
}, 'low');
await t('모르는 필드는 안 넘어간다', async () => {
  await post({ ...good, tools: [{ name: 'evil' }], temperature: 2 });
  return JSON.stringify(Object.keys(sent.body).sort());
}, JSON.stringify(['max_tokens', 'messages', 'model', 'output_config', 'system'].sort()));

console.log('\n=== 잘못된 입력 ===');
await t('JSON 이 아니면 400', async () => (await post('not json')).status, 400);
await t('messages 없으면 400', async () => (await post({ max_tokens: 10 })).status, 400);
await t('messages 가 9개면 400', async () => (await post({ ...good,
  messages: Array(9).fill({ role: 'user', content: 'x' }) })).status, 400);
await t('role 이 이상하면 400', async () => (await post({ ...good,
  messages: [{ role: 'system', content: 'x' }] })).status, 400);
await t('content 가 글자가 아니면 400', async () => (await post({ ...good,
  messages: [{ role: 'user', content: { a: 1 } }] })).status, 400);
await t('본문이 256KB 넘으면 413', async () => (await post({ ...good,
  system: 'x'.repeat(300 * 1024) })).status, 413);
await t('키가 없으면 500', async () => (await onRequestPost({
  request: new Request('https://x', { method: 'POST', body: JSON.stringify(good) }),
  env: {} })).status, 500);
await t('GET 은 405', async () => (await onRequestGet()).status, 405);

console.log('\n=== 응답에 키가 섞이지 않는가 ===');
const body = await (await post(good)).text();
await t('응답 본문에 키 없음', async () => body.includes('sk-ant-'), false);

console.log(`\n통과 ${pass}  실패 ${fail}`);
process.exit(fail ? 1 : 0);
