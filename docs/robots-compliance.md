# 수집 대상 사이트 robots.txt 확인 기록

확인일: 2026-09-06

| 사이트 | `User-agent: *` 규칙 | 일반 수집기 허용 여부 |
|---|---|---|
| 무신사 (musinsa.com) | `Disallow: /` | **불가** — 화이트리스트 방식 |
| W컨셉 (wconcept.co.kr) | (명시 없음, 화이트리스트 전용) | **불가** |
| 29CM (29cm.co.kr) | `Allow: /` (마이페이지, 주문, 인증 등만 차단) | 가능 |
| 지그재그 (zigzag.kr) | `Allow: /` (GPTBot만 차단) | 당시 가능 → **2026-11-05 재확인 결과 불가.** 아래를 본다 |
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

본 프로젝트가 만드는 수집기는 Group 1과 2 어디에도 해당하지 않으므로 Group 4가 적용된다.
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

## 데이터랩 API 접근 경로 (2026-09-15 확인)

수집은 공식 API 로만 한다. 단, 데이터랩 API 는 developers.naver.com 이 아니라
네이버 클라우드 플랫폼의 NAVER API HUB 를 통해 제공된다.

    호스트   https://naverapihub.apigw.ntruss.com
    인증     X-NCP-APIGW-API-KEY-ID / X-NCP-APIGW-API-KEY
    경로     /search-trend/v1/search
             /shopping/v1/categories
             /shopping/v1/category/{device,gender,age}
             /shopping/v1/category/keywords
             /shopping/v1/category/keyword/{device,gender,age}

예전 방식(openapi.naver.com + X-Naver-Client-*)으로 부르면 키가 유효해도
401 NID AUTH Result Invalid 가 난다. 경로는 공개 문서에 전부 나와 있지 않아
실제 호출로 확인했다.

## 네이버 쇼핑 분류 체계 메모 (2026-09-15 확인)

패션의류 > 남성의류 아래 3단계 분야는 니트 / 티셔츠 / 셔츠와 남방 / 아우터 / 점퍼 /
청바지 / 바지 / 정장세트 / 트레이닝복 / 한복 등이다. **후드티와 맨투맨은 별도
분야로 존재하지 않는다.**

티셔츠 분야(50000169) 안에서 키워드별 클릭 지수를 한 요청으로 비교한 결과
(2026-08-14 ~ 09-14 평균):

    후드티 37.1 / 반팔티 30.4 / 맨투맨 22.9 / 긴팔티 9.7 / 니트 3.0

후드티와 맨투맨이 티셔츠 분야 안에서 강하게 잡히고, 별도 분야인 니트는 거의
잡히지 않는다. 따라서 1차 분석 범위(티셔츠, 후드, 맨투맨)는 티셔츠 분야 하나로
덮이며, 세부 구분은 분야 코드가 아니라 키워드로 한다.

## 쇼핑인사이트 인구통계의 편향 (2026-09-15 확인)

여성과 남성 티셔츠 분야 모두 최다 연령대가 40대로 나온다.

    50000167 여성>티셔츠   여성 69.5 / 남성 2.2    최다 40대 (64.2)
    50000169 남성>티셔츠   남성 44.1 / 여성 15.3   최다 40대 (42.4)

성별 구분은 분야와 정확히 일치하지만, 연령 분포는 네이버쇼핑 이용자층을 반영한
값이지 무신사 이용자층이 아니다. 무신사는 20대 비중이 훨씬 높다.

따라서 연령 분포를 절대적인 기준으로 쓰면 안 된다. "특정 연령에 국한된 현상인가"를
판단할 때는 같은 채널 안에서 **다른 키워드 대비 상대적으로** 치우쳤는지를 봐야 하며,
채널 자체의 기저 분포를 먼저 구해 비교 기준으로 삼아야 한다.

## 29CM API 의 클라우드 IP 차단 (2026-09-27 확인)

GitHub Actions 러너에서 호출하면 403 이 온다. 같은 코드와 같은 User-Agent 로
로컬에서 호출하면 200 이다. 클라우드 IP 대역 차단으로 보인다.

2026-09-09 ~ 09-15 동안 예약 실행 16회가 전부 실패했고 그 기간 데이터는
소급 수집이 불가능하다. 예약 실행을 걷어내고 수집을 로컬로 옮겼다.
scripts/install_local_schedule.sh 참고.

robots.txt 는 여전히 허용 범위 안이다(29CM 는 `User-agent: * → Allow: /`).
차단은 robots 규칙이 아니라 인프라 수준의 접근 제어로 판단된다.

## 재확인 2026-11-05

두 달 만에 다시 받아 봤다. **지그재그가 바뀌었다.** 9월에는 와일드카드가
열려 있었는데 지금은 무신사와 같은 화이트리스트 구조다.

```
User-agent: Googlebot, bingbot, Yeti, NaverBot, Applebot,
            OAI-SearchBot, Claude-SearchBot, PerplexityBot,
            ChatGPT-User, Claude-User, facebookexternalhit, ...
Allow: /
Disallow: /auth, /checkout, /inbox, /*/__preview/

User-agent: AhrefsBot, GPTBot, ClaudeBot, CCBot, Baiduspider,
            Google-Extended, Applebot-Extended, GoogleOther, ...
Disallow: /

User-agent: *
Disallow: /
```

본 프로젝트 수집기는 마지막 그룹에 걸린다. **지그재그 자체 크롤링은
허용되지 않는다.** 11월 역할 분담에 적어 둔 "지그재그 수집" 은 그대로
진행할 수 없고 대체 소스를 쓴다.

robots.txt 는 바뀌는 파일이다. 한 번 확인하고 끝내면 안 되고 수집기를
새로 붙일 때마다 다시 받아야 한다.

### 대체 후보 8곳 (2026-11-05 확인)

| 사이트 | `User-agent: *` 규칙 | 일반 수집기 |
|---|---|---|
| 지그재그 (zigzag.kr) | `Disallow: /` | 불가 |
| SSF샵 (ssfshop.com) | `Disallow: /` | 불가 |
| EQL (eqlstore.com) | `Disallow: /`, 루트만 허용 | 불가 |
| LF몰 (lfmall.co.kr) | `Disallow: /` | 불가 |
| 에이블리 (a-bly.com) | `Allow: /$`, `Allow: /app*`, `Disallow: /` | `/app*` 만. 실제로는 403 |
| 브랜디 (brandi.co.kr) | `Disallow: /products/*` | 목록은 허용 |
| 하이버 (hiver.co.kr) | `Disallow: /products/*`, `/store/*`, `/search`, `/api/` | 목록은 허용 |
| 코오롱몰 (kolonmall.com) | **그룹 자체가 없다** | 제한 규칙 없음 |

코오롱몰에는 `User-agent: *` 그룹이 아예 없다. RFC 9309 는 내 수집기에
맞는 그룹이 하나도 없으면 제한 규칙이 없는 것으로 읽는다. 다만 이것은
명시적 허락이 아니라 규칙의 부재다. 29CM 의 `Allow: /` 와는 성격이
다르므로 보고서에 쓸 때 구분해서 적는다.

### 자료가 실제로 받아지는지 (2026-11-05 확인)

robots 가 열려 있어도 자료가 서버 응답에 없으면 못 쓴다. 목록 페이지를
한 번씩 받아 봤다.

    브랜디      모든 경로가 같은 181KB 껍데기다. 내부 API 없이는 불가
    에이블리     /app/best 가 403 이다
    하이버      /ranking 이 서버 렌더링이고 __NEXT_DATA__ 에 50건이 있다
                흠: seller 가 판매 법인명이고 브랜드가 아니다
                흠: root_category 가 매장 구분이고 의류 분류가 아니다
    코오롱몰     /Best 가 서버 렌더링이고 100건이 있다
                순위, 브랜드, 상품명, 정가, 판매가, 리뷰 수, 상품코드
                카테고리별 목록이 productListNo 와 categoryCode 로 나뉘어 있다
