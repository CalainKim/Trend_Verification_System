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

## 네이버 데이터랩 (2026-09-08 확인)

`datalab.naver.com/robots.txt`

```
User-Agent: *
Allow: /$
Allow: /index.naver
Disallow: /
```

루트와 index 를 제외한 전 경로가 차단이다. 쇼핑인사이트 카테고리 코드를 돌려주는
내부 엔드포인트(`/shoppingInsight/getCategory.naver`)도 여기에 포함되므로
**자동 조회하지 않는다.**

카테고리 코드는 브라우저에서 쇼핑인사이트 분야 선택 화면을 직접 보고 확인해
`collectors/naver_shopping.py` 의 `TOPS_CATEGORIES` 에 상수로 적어 넣는다.
값이 자주 바뀌지 않는 식별자라 일회성 확인으로 충분하다.

데이터 수집 자체는 `openapi.naver.com` 의 공식 오픈 API 로만 한다.
공식 API 는 별도 이용 신청과 키 발급을 거친 정상 경로이며 robots.txt 대상이 아니다.
