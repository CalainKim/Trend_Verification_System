# 웹 배포

v9 화면을 승인된 사람만 들어오는 웹 주소로 올린다. 2026-11-05 에 정했고
근거를 함께 남긴다.

`docs/paper-and-release.md` 가 2026-11-03 에 GitHub Pages 를 1순위로 적었다.
그 결론은 **읽기만 하는 화면**을 전제로 한 것이다. 심층 검증 버튼이 실제로
돌아야 한다는 요구가 생기면서 전제가 바뀌었다. Pages 는 서버에서 코드를
돌릴 수 없어 후보에서 빠진다.

---

## 1. 무엇을 배포하나

```
build/web/index.html                 랜딩. 누구나 본다
build/web/assets/                    랜딩의 로고, 글꼴, 첫 화면 3D 영상
build/web/login.html                 비밀번호 입력 창
build/web/app/index.html             모니터 시안 한 파일. 6.4MB
build/web/functions/_middleware.js   비밀번호 게이트
build/web/functions/auth/            로그인, 로그아웃
build/web/functions/api/complete.js  심층 검증 중계
```

전부 `./scripts/build_web.sh` 가 만든다. 모니터 원본은 `design/Trend Monitor
v9.dc.html` 과 `design/runtime/`, 랜딩 원본은 `design/landing/` 이다.

2026-11-08 에 랜딩을 첫 화면으로 올리고 모니터를 `/app/` 으로 옮겼다.
프로젝트 소개용이라 랜딩은 공개해도 된다고 정했다. 모니터와 중계는 키를
쓰므로 계속 승인된 사람만 들어온다. 중계 주소는 `/api/complete` 절대경로라
모니터 위치가 바뀌어도 그대로 닿는다.

첫 화면 3D 영상은 Blender 로 렌더한다. 넓은 화면용은 `assets/hero/`, 세로
화면용은 `assets/hero/m/` 에 두고, 랜딩이 화면 비율을 보고 고른다. 영상이
없으면 캔버스로 그린 장면이 대신 돈다.

## 2. 왜 Cloudflare 인가

요구가 "승인된 사람만" 이라 접근 제한이 선택을 갈랐다.

```
                 중계 서버   접근 제한            비용
Cloudflare       된다        Access 50명까지      0원
Vercel           된다        Pro + 비밀번호       월 $40
GitHub Pages     안 된다     해당 없음            0원
```

Vercel 비밀번호 보호는 Pro 플랜에서 프로젝트당 월 $20 이고 Pro 자체가 월
$20 다. Cloudflare Zero Trust 는 50명까지 무료이고 이메일 허용 목록으로
승인된 사람만 들여보낸다. 정적 요청은 무제한 무료, Functions 는 하루 10만
요청까지 무료다.

Workers 는 CPU 시간을 재고 대기 시간은 재지 않는다. Claude 호출은 몇 초가
걸려도 대부분이 네트워크 대기라서 무료 등급의 CPU 한도에 걸리지 않는다.

## 3. 키가 새지 않는 구조

키를 화면에 심는 선택지는 두지 않았다. 비밀번호로 사람을 걸러도 안전해지지
않기 때문이다.

```
키를 화면에 심으면   들어온 사람이 소스 보기로 읽을 수 있다
읽힌 뒤에는          게이트 밖에서 영구히 쓰인다. 호출 제한도 못 건다
키를 서버에만 두면   승인을 취소하는 순간 호출도 끊긴다
```

게이트는 문을 지키지만 열쇠를 복사해 나가는 것은 막지 못한다. 그래서 중계를
둔다.

막는 자리를 셋으로 나눠 두었다.

```
bundle_design.py   --relay 와 --embed-key 를 같이 주면 멈춘다
build_web.sh       배포 폴더에서 실제 키 모양을 찾으면 멈춘다
complete.js        키를 응답에 넣지 않는다
```

## 4. 중계가 막는 것은 횟수가 아니라 내용이다

비밀번호는 사람을 거르지만 들어온 사람이 보내는 내용은 거르지 않는다. 화면을
고쳐서 비싼 모델이나 큰 한도를 보낼 수 있다. 그래서 받은 것을 그대로 넘기지
않고 서버가 필드를 하나씩 골라 담는다.

```
모델          허용 목록에 없으면 기본값으로 떨어진다
max_tokens    4000 에서 자른다. 시안이 쓰는 최대는 3000 이다
effort        low, medium, high 외에는 low 로
본문 크기     256KB 에서 거부한다
messages      8개까지, role 과 content 모양을 직접 확인한다
모르는 필드    통째로 버린다. tools 나 temperature 는 넘어가지 않는다
```

`web/functions/api/complete.test.mjs` 가 이것들을 14가지로 검사하고
`pytest tests/test_relay_function.py` 로 같이 돌아간다.

## 5. 처음 한 번 하는 설정

내 손으로 해야 하는 부분이다.

```
1  Cloudflare 계정을 만든다 (무료)

2  Pages 프로젝트를 만든다
   npx wrangler pages project create trend-monitor

3  환경변수를 넣는다. 대시보드 Settings > Variables and Secrets
   ANTHROPIC_API_KEY   암호(Secret) 로 넣는다. 일반 변수로 넣으면 안 된다
   CLAUDE_MODEL        비워 두면 claude-sonnet-5-5 를 쓴다

4  비밀번호 게이트의 비밀값 둘을 같은 곳에 암호(Secret) 로 넣는다
   SITE_PASSWORD    들어올 사람에게 알려 줄 비밀번호. 짧은 단어보다 길게
   SESSION_SECRET   쿠키 서명용 임의 문자열. openssl rand -base64 32 로 만든다

5  예전에 Zero Trust > Access 로 주소를 감쌌다면 풀거나 /app 과 /api 로 좁힌다
   주소 전체를 감싸 두면 랜딩과 비밀번호 입력 창까지 막힌다
```

4번의 두 값이 없으면 게이트가 /app 과 /api 를 열지 않고 500 을 낸다. 빠뜨린
채 올려도 열린 채로 배포되지는 않는다.

## 5.2 심층 검증 스위치

심층 검증 버튼은 Claude API 를 부르고 쓴 만큼 돈이 든다. 그래서 평소에는
닫아 두고 교수님 미팅 같은 시연 때만 연다. 2026-11-08 에 정했다.

```
./scripts/relay.sh open 2h                 지금부터 2시간 연다 (90m 도 된다)
./scripts/relay.sh open 2026-11-12T16:00   이 시각까지 연다 (한국 시각)
./scripts/relay.sh close                   바로 닫는다
```

스크립트는 비밀값 `RELAY_OPEN_UNTIL` 에 마감 시각을 넣고 다시 배포한다.
중계(`complete.js`)는 키를 보기 전에 이 값을 먼저 확인한다.

```
값이 없다           닫힘. 처음 배포한 상태가 이것이다
마감 시각이 지났다   닫힘. 닫는 것을 잊어도 저절로 닫힌다
읽을 수 없다         닫힘
마감 전이다          열림
```

닫혀 있으면 Anthropic 에 요청이 한 번도 나가지 않고 화면에는 "심층 검증은
지금 닫혀 있습니다" 가 뜬다. 한 번에 12시간보다 길게 열지 못하게 해서
미팅 날짜를 미리 넣어 둘 수는 없다. 미팅 당일에 연다.

## 5.1 비밀번호 게이트

2026-11-08 에 Cloudflare Access(메일 인증) 대신 비밀번호 입력 방식으로 바꿨다.
들어올 사람에게 메일 주소를 받지 않고 비밀번호 하나만 알려 주면 되기 때문이다.

```
/            랜딩. 누구나
/login       비밀번호 입력 창. 누구나
/app/        모니터. 로그인한 사람만. 아니면 /login 으로 보낸다
/api/        중계. 로그인한 사람만. 아니면 401
/auth/login  입력 창이 비밀번호를 보내는 곳
/auth/logout 쿠키를 지우고 랜딩으로
```

막는 자리는 화면이 아니라 서버(`functions/_middleware.js`)다. 화면에서 막으면
주소를 직접 치거나 소스를 보고 넘어갈 수 있다.

```
쿠키          "만료시각.서명". SESSION_SECRET 으로 서명해 밖에서 만들 수 없다
유지 기간     7일. HttpOnly, Secure, SameSite=Lax
비밀번호 변경  서명에 비밀번호 해시를 섞어 두어 이전 쿠키가 모두 무효가 된다
틀렸을 때     0.6초 늦게 답한다. 무료 등급에서 횟수 제한을 걸기 어려워서다
돌아갈 곳     같은 사이트 안의 경로만. //다른사이트 로 내보내지 않는다
```

`web/functions/auth.test.mjs` 가 27가지로 검사하고 `pytest
tests/test_auth_gate.py` 로 같이 돈다.

로컬에서 끝까지 확인하려면 비밀값을 파일이 아니라 옵션으로 넣는다.

```
cd build/web
npx wrangler pages dev . --binding SITE_PASSWORD="시험용" --binding SESSION_SECRET="시험용"
```

`build/web` 안에 `.dev.vars` 를 두면 `/.dev.vars` 주소로 그대로 내려받아진다.
2026-11-08 에 실제로 확인했다. 그래서 빌드 스크립트가 배포 폴더에서 이런
파일을 찾으면 멈춘다.

## 6. 올리고 갱신하기

```
./scripts/build_web.sh
cd build/web && npx wrangler pages deploy .
```

시안을 다시 받거나 모델을 바꾸면 같은 두 줄을 다시 돌린다.
`build/` 는 저장소에 들어가지 않으므로 올리는 것은 항상 방금 만든 것이다.

**반드시 `build/web` 안에서 돌린다.** wrangler 는 `functions/` 를 실행 위치
기준으로 찾는다. 바깥에서 `wrangler pages deploy build/web` 로 돌리면
`No Functions. Shimming...` 만 적고 중계 없이 올라간다. 화면은 올라가지만
심층 검증 버튼이 조용히 죽는다. 2026-11-05 에 실제로 겪었다.

## 6.1 wrangler 명령에 주의할 것

`wrangler pages project create` 는 이름만 보면 프로젝트만 만들 것 같지만
그렇지 않다. 2026-11-05 에 돌려 보니 이렇게 했다.

```
wrangler.jsonc 를 자동 생성한다   "assets": { "directory": "docs" }
그 설정으로 즉시 배포한다          docs/ 전체 39개 파일을 올린다
.gitignore 에 줄을 덧붙인다        .wrangler 와 .dev.vars
```

`docs` 는 wrangler 가 추측한 값이고 우리가 올릴 폴더가 아니다. `docs/` 에는
저장소에서 제외한 로컬 전용 파일이 들어 있다.

2026-11-08 에 다시 만들 때는 계정에 프로젝트가 없었다. wrangler 4.158 은
`pages project create` 를 새 Workers 방식으로 넘기려다 빈 폴더라 실패한다.
우리는 `functions/` 를 쓰는 기존 Pages 방식이라 `--force` 를 붙여 만들었다.
설정 파일이 없는 빈 폴더에서 돌려 아무것도 올라가지 않게 했다.

```
mkdir 빈폴더 && cd 빈폴더
npx wrangler pages project create trend-monitor --production-branch main --force
```

`--force` 는 만들 때 한 번만 쓴다. 그 뒤의 `pages deploy` 와 `pages secret`
은 붙이지 않아도 기존 Pages 로 간다.


```
docs/images/figures/      보고서 그림. .gitignore:43
docs/report-figures.html  보고서 중간 산출물
```

그래서 저장소 루트에 `wrangler.jsonc` 를 두지 않는다. 설정은
`build_web.sh` 가 `build/web` 안에 만든다. 루트에서 wrangler 를 돌려야 할
일이 생기면 무엇을 올리는지 먼저 확인한다.

## 7. 모델

```
시안에 박힌 것    claude-sonnet-4-5
실제로 쓰는 것    claude-sonnet-5-5
```

시안은 Claude Design 에서 다시 받아오는 파일이라 원본을 손으로 고치면 다음
수령 때 되살아난다. 가운뎃점을 빌드할 때마다 지우는 것과 같은 이유로 모델도
빌드 시점에 바꾼다. `bundle_design.py` 의 `swap_model` 이 그 자리다.

중계판에서는 서버가 모델을 다시 정하므로 화면이 보내는 값이 최종 결정은
아니다. 그래도 바꿔 두는 이유는 파일 사본(`--embed-key`)이 서버를 거치지 않아
그 값을 그대로 쓰기 때문이다.

## 8. 파일 사본과 무엇이 다른가

둘 다 유지한다. 쓰는 자리가 다르다.

```
                  파일 사본                     웹 배포판
만드는 법          bundle_design.py              bundle_design.py --relay
심층 검증          보는 사람이 키를 넣는다        서버가 대신 부른다
키                 화면에 없다                   서버에만 있다
접근 제한          파일을 받은 사람              Access 허용 목록
쓰는 자리          인터넷 없는 자리, 손으로 전달   링크 공유
```

`--embed-key` 로 만드는 사본은 내 컴퓨터 전용이다. 파일 이름에 `로컬` 이
들어가야 만들어지고, 남에게 보내면 키가 샌다.

## 9. 코드 위치

```
scripts/build_web.sh                    배포 폴더를 만든다
scripts/bundle_design.py                시안을 한 파일로 묶는다
  RELAY_SHIM                            중계판이 쓰는 window.claude
  BROWSER_SHIM                          파일 사본이 쓰는 window.claude
  swap_model                            모델 이름을 바꾼다
web/functions/api/complete.js           중계 함수
web/functions/api/complete.test.mjs     중계 함수 검사
tests/test_relay_function.py            위 검사를 pytest 로 묶는다
```
