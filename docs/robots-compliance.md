# 수집 대상 사이트 robots.txt 확인 기록

확인일: 2026-09-06

| 사이트 | `User-agent: *` 규칙 | 일반 수집기 허용 여부 |
|---|---|---|
| 무신사 (musinsa.com) | `Disallow: /` | **불가** — 화이트리스트 방식 |
| W컨셉 (wconcept.co.kr) | (명시 없음, 화이트리스트 전용) | **불가** |
| 29CM (29cm.co.kr) | `Allow: /` (마이페이지·주문·인증 등만 차단) | 가능 |
| 지그재그 (zigzag.kr) | `Allow: /` (GPTBot만 차단) | 가능 |
| 에이블리 (ably.co.kr) | robots.txt 응답 없음 | 명시 규칙 없음 — 이용약관 별도 확인 필요 |

## 무신사 상세

robots.txt(최종 갱신 2026.05.13)는 화이트리스트 구조다.

- Group 1 (전면 허용): Applebot, facebookexternalhit, Twitterbot, OAI-SearchBot,
  ChatGPT-User, Claude-User, Claude-SearchBot, Perplexity-User
- Group 2 (부분 허용): Googlebot, Yeti, NaverBot, Daum, Bingbot, CCBot, GPTBot,
  ClaudeBot, PerplexityBot, Amazonbot 등 — `/auth/`, `/mypage/`, `/like/`,
  `/showcase/`, `/fashiontalk/`, `/festival/` 제외 허용
- Group 3: Baiduspider 전면 차단
- Group 4 (와일드카드 폴백): `User-agent: * → Disallow: /`

본 프로젝트가 만드는 수집기는 Group 1·2 어디에도 해당하지 않으므로 Group 4가 적용된다.
즉 **무신사 랭킹 페이지의 자체 크롤링은 robots.txt상 허용되지 않는다.**

## 결론

무신사를 트랙 B 소스로 쓰려면 연계 산업체 채널을 통한 **명시적 수집 허가(또는 데이터 제공)**
가 선행되어야 한다. 허가 이전 기간에는 robots.txt가 일반 수집기를 허용하는 사이트를
대체 소스로 사용한다.
