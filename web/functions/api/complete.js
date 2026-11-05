// 심층 검증 중계. 화면이 /api/complete 로 보내면 여기서 Claude 를 부른다.
//
// 왜 중계를 두는가
// ---------------
// 키를 화면에 심으면 비밀번호로 사람을 걸러도 안전해지지 않는다. 들어온
// 사람이 소스에서 키를 읽어 가면 그 뒤로는 게이트 밖에서 영구히 쓰이고,
// 접근을 취소해도 호출은 계속된다. 키를 서버에만 두면 승인을 내리는 순간
// 호출도 끊긴다.
//
// 받은 것을 그대로 넘기지 않는 이유
// -----------------------------
// body 를 통째로 전달하면 열린 중계가 된다. 화면을 고쳐서 비싼 모델이나 큰
// max_tokens 를 보내는 길이 열린다. 게이트는 사람을 거르지만 그 사람이 보내는
// 내용은 거르지 않는다. 그래서 필드를 하나씩 골라 담고 상한을 여기서 박는다.
//
// 환경변수
//   ANTHROPIC_API_KEY   필수. Cloudflare 대시보드에서 암호로 넣는다
//   CLAUDE_MODEL        선택. 기본값은 아래 DEFAULT_MODEL

const DEFAULT_MODEL = 'claude-sonnet-5-5';

// 화면이 보내는 이름을 그대로 믿지 않는다. 목록에 없으면 기본값으로 떨어진다.
const ALLOWED_MODELS = new Set([
  'claude-sonnet-5-5',
  'claude-opus-5-5',
  'claude-haiku-5-5',
]);

// 시안이 쓰는 가장 큰 값이 3000 이다. 조금 여유를 두고 막는다.
const MAX_TOKENS_CAP = 4000;
const MAX_BODY_BYTES = 256 * 1024;
const MAX_MESSAGES = 8;
const ALLOWED_EFFORT = new Set(['low', 'medium', 'high']);

const json = (obj, status) => new Response(JSON.stringify(obj), {
  status,
  headers: { 'content-type': 'application/json; charset=utf-8' },
});

const fail = (status, message) => json({ error: { message } }, status);

export async function onRequestPost({ request, env }) {
  if (!env.ANTHROPIC_API_KEY) {
    return fail(500, '서버에 ANTHROPIC_API_KEY 가 설정되지 않았습니다.');
  }

  const raw = await request.text();
  if (raw.length > MAX_BODY_BYTES) {
    return fail(413, '요청이 너무 큽니다.');
  }

  let body;
  try {
    body = JSON.parse(raw);
  } catch (e) {
    return fail(400, '요청 본문이 JSON 이 아닙니다.');
  }

  // messages 는 모양을 직접 확인한다. 통과시킨 뒤 Anthropic 이 400 을 주면
  // 화면에는 이유 없는 실패로 보인다.
  const messages = body.messages;
  if (!Array.isArray(messages) || messages.length === 0) {
    return fail(400, 'messages 가 없습니다.');
  }
  if (messages.length > MAX_MESSAGES) {
    return fail(400, 'messages 가 너무 많습니다.');
  }
  for (const m of messages) {
    if (!m || typeof m !== 'object') return fail(400, 'messages 모양이 잘못됐습니다.');
    if (m.role !== 'user' && m.role !== 'assistant') {
      return fail(400, 'messages 의 role 이 잘못됐습니다.');
    }
    if (typeof m.content !== 'string' || m.content.length === 0) {
      return fail(400, 'messages 의 content 가 글자가 아닙니다.');
    }
  }

  const model = ALLOWED_MODELS.has(body.model)
    ? body.model
    : (env.CLAUDE_MODEL || DEFAULT_MODEL);

  let maxTokens = Number(body.max_tokens);
  if (!Number.isFinite(maxTokens) || maxTokens <= 0) maxTokens = 2500;
  maxTokens = Math.min(Math.floor(maxTokens), MAX_TOKENS_CAP);

  // 생각 분량도 max_tokens 에서 깎인다. effort 를 넘기지 않으면 모델이 알아서
  // 길게 생각하다 한도에 걸려 본문이 한 글자도 안 나온다. 시안이 low 를 보내는
  // 이유가 그것이고, 안 오면 여기서 채운다.
  const effort = ALLOWED_EFFORT.has((body.output_config || {}).effort)
    ? body.output_config.effort
    : 'low';

  const out = {
    model,
    max_tokens: maxTokens,
    output_config: { effort },
    messages: messages.map((m) => ({ role: m.role, content: m.content })),
  };
  if (typeof body.system === 'string' && body.system.length > 0) {
    out.system = body.system;
  }

  let res;
  try {
    res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-api-key': env.ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify(out),
    });
  } catch (e) {
    return fail(502, 'Anthropic API 에 연결하지 못했습니다.');
  }

  const text = await res.text();
  if (!res.ok) {
    // 원문을 그대로 돌려준다. 모델 이름이나 한도 문제는 여기에만 적혀 있고,
    // 삼키면 화면에서 원인을 찾을 수 없다. 키는 응답에 들어가지 않는다.
    return new Response(text, {
      status: res.status,
      headers: { 'content-type': 'application/json; charset=utf-8' },
    });
  }
  return new Response(text, {
    status: 200,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'no-store',
    },
  });
}

// GET 으로 열어 보는 사람에게 설명을 준다. 404 면 배포가 안 된 것으로 오해한다.
export async function onRequestGet() {
  return fail(405, '이 주소는 화면이 POST 로만 부릅니다.');
}
