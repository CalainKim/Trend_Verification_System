# 라이브 데모 명령어

프로젝트 폴더에서 실행한다.

    cd "/Users/kim_doeun/[자주프]Trend_Signal_Verification_System"
    source .env

---

## 1. 원본 — 네이버 API 응답

    curl -s -X POST "https://naverapihub.apigw.ntruss.com/search-trend/v1/search" \
      -H "X-NCP-APIGW-API-KEY-ID: $NAVER_CLIENT_ID" \
      -H "X-NCP-APIGW-API-KEY: $NAVER_CLIENT_SECRET" \
      -H "Content-Type: application/json" \
      -d '{"startDate":"2026-09-01","endDate":"2026-09-07","timeUnit":"date","keywordGroups":[{"groupName":"맨투맨","keywords":["맨투맨"]}]}' | jq

ratio 는 절대 검색량이 아니라 이 응답 안에서 최댓값=100 으로 정규화된 값이다.

성별·연령 교차 조건을 걸어본다. 값이 달라지는 것을 확인한다.

    curl -s -X POST "https://naverapihub.apigw.ntruss.com/search-trend/v1/search" \
      -H "X-NCP-APIGW-API-KEY-ID: $NAVER_CLIENT_ID" \
      -H "X-NCP-APIGW-API-KEY: $NAVER_CLIENT_SECRET" \
      -H "Content-Type: application/json" \
      -d '{"startDate":"2026-09-01","endDate":"2026-09-07","timeUnit":"date","gender":"m","ages":["3","4"],"keywordGroups":[{"groupName":"맨투맨","keywords":["맨투맨"]}]}' | jq '.results[0].data'

---

## 2. 원본 — 29CM 랭킹 API

    curl -s -A "TrendSignalResearchBot/0.1" -H "Referer: https://www.29cm.co.kr/" \
      "https://recommend-api.29cm.co.kr/api/v4/best/items?categoryList=272103100&periodSort=ONE_DAY&limit=3&offset=0" | jq

필요한 필드만 본다.

    curl -s -A "TrendSignalResearchBot/0.1" -H "Referer: https://www.29cm.co.kr/" \
      "https://recommend-api.29cm.co.kr/api/v4/best/items?categoryList=272103100&periodSort=ONE_DAY&limit=10&offset=0" \
      | jq -r '.data.content[] | "\(.itemName)\t\(.frontBrandNameKor)\t리뷰\(.reviewCount)\t좋아요\(.heartCount)"'

---

## 3. 저장 원본 — 관측일별 CSV

    ls -la data/snapshots/commerce_rank/
    head -3 data/snapshots/commerce_rank/*.csv | cut -c1-160
    wc -l data/snapshots/commerce_rank/*.csv

SQLite 는 이 CSV 에서 다시 만들 수 있는 파생물이다.

---

## 4. DB 에 직접 들어가서 자유롭게 질의

    sqlite3 data/signals.sqlite

들어가면 프롬프트가 `sqlite>` 로 바뀐다. SQL 을 그대로 치면 된다.
`~/.sqliterc` 에 헤더·컬럼 정렬을 켜 두었으므로 결과가 표로 나온다.

    sqlite> .tables
    sqlite> .schema signal_raw
    sqlite> SELECT * FROM signal_raw LIMIT 5;
    sqlite> .quit

### 질의를 짤 때 알아야 할 값

채널

    naver_datalab    검색어 트렌드
    naver_shopping   쇼핑 클릭
    gtrends          Google Trends
    commerce_rank    29CM 랭킹

metric_type

    search_index     검색 지수
    click_index      클릭 지수
    rank             순위 (작을수록 상위)
    review_count     리뷰 수
    heart_count      좋아요 수

entity (하위 구분)

    (빈 문자열)          전체
    gender=m / f        성별 (주변분포)
    age=10 ~ age=60     연령 (주변분포)
    gender=m;ages=3+4   20대 남성 (교차셀)
    geo=KR / US / WORLD 지역
    29cm:<번호>          커머스 상품
    29cm:<번호>@<코드>    커머스 상품의 랭킹 내 순위

keyword_raw 가 `category:50000169` 인 행은 분야 전체 기준선이다.

### 즉석에서 쓸 만한 질의

특정 키워드의 최근 추이

    SELECT substr(observed_at,1,10) d, round(metric_value,1) v
    FROM signal_raw
    WHERE keyword_raw='럭비티' AND channel='naver_datalab' AND entity=''
    ORDER BY d DESC LIMIT 20;

오늘 순위가 가장 많이 오른 상품

    SELECT keyword_raw,
           MIN(CASE WHEN observed_at LIKE '2026-09-27%' THEN metric_value END) AS before_,
           MIN(CASE WHEN observed_at LIKE '2026-09-29%' THEN metric_value END) AS after_
    FROM signal_raw WHERE channel='commerce_rank' AND metric_type='rank'
    GROUP BY keyword_raw
    HAVING before_ IS NOT NULL AND after_ IS NOT NULL AND before_ - after_ > 20
    ORDER BY before_ - after_ DESC LIMIT 15;

품절된 상품

    SELECT DISTINCT keyword_raw, json_extract(metadata,'$.brand_kor') brand
    FROM signal_raw
    WHERE channel='commerce_rank' AND json_extract(metadata,'$.sold_out')=1
    LIMIT 15;

metadata 안을 들여다보기

    SELECT json_extract(metadata,'$.brand_kor') brand,
           json_extract(metadata,'$.category3') cat,
           json_extract(metadata,'$.sale_price') price,
           keyword_raw
    FROM signal_raw WHERE channel='commerce_rank' AND metric_type='rank'
    ORDER BY metric_value LIMIT 15;

20대 남성만 따로 보기

    SELECT substr(observed_at,1,10) d, channel, round(metric_value,1) v
    FROM signal_raw WHERE entity LIKE '%ages=%' AND entity LIKE 'gender=m%'
    ORDER BY d DESC LIMIT 20;

한 상품의 리뷰가 늘어나는 것

    SELECT substr(observed_at,1,10) d, metric_value reviews
    FROM signal_raw
    WHERE channel='commerce_rank' AND metric_type='review_count'
      AND keyword_raw LIKE '%LAUNDRY SHIRT%' ORDER BY d;

---

## 5. DB 구조

    sqlite3 data/signals.sqlite ".tables"
    sqlite3 data/signals.sqlite ".schema signal_raw"

---

## 6. 무엇이 얼마나 쌓였나

    sqlite3 -header -column data/signals.sqlite "
      SELECT channel, COUNT(*) rows, COUNT(DISTINCT keyword_raw) keywords,
             MIN(substr(observed_at,1,10)) first, MAX(substr(observed_at,1,10)) last
      FROM signal_raw GROUP BY channel;"

---

## 7. 시점을 두 개로 나눈 이유

    sqlite3 -header -column data/signals.sqlite "
      SELECT substr(observed_at,1,10) observed, substr(collected_at,1,10) collected,
             channel, keyword_raw, round(metric_value,1) val
      FROM signal_raw WHERE channel='naver_datalab' AND observed_at < '2022-01-01' LIMIT 5;"

2021 년 자료를 2026 년에 수집했다. 한 컬럼이면 전부 '오늘 관측'이 된다.

---

## 8. entity 하나로 모든 세그먼트를 담는다

    sqlite3 -header -column data/signals.sqlite "
      SELECT DISTINCT entity FROM signal_raw
      WHERE channel IN ('naver_datalab','naver_shopping','gtrends') ORDER BY entity;"

교차셀(gender=m;ages=3+4)과 주변분포(gender=m)가 구분되어 있다.

    sqlite3 -header -column data/signals.sqlite "
      SELECT substr(observed_at,1,10) obs, entity, round(metric_value,1) val
      FROM signal_raw WHERE keyword_raw='럭비티' AND channel='naver_datalab'
        AND observed_at LIKE '2024-07-1%' ORDER BY obs, entity LIMIT 20;"

---

## 9. 수집 원본 상품명 — 날 것

    sqlite3 data/signals.sqlite "
      SELECT DISTINCT keyword_raw FROM signal_raw
      WHERE channel='commerce_rank' ORDER BY RANDOM() LIMIT 30;"

프로모션 태그, 배송 차수, 품번, 색상이 섞여 있다.

---

## 10. 정제 — 정규화 전후

    .venv/bin/python -c "
    import sys; sys.path.insert(0,'src')
    from trend_pipeline import embeddings as e, storage
    for (n,) in storage.connect().execute(\"SELECT DISTINCT keyword_raw FROM signal_raw WHERE channel='commerce_rank' ORDER BY RANDOM() LIMIT 20\"):
        c = e.normalize_for_embedding(n)
        print(f'{n[:58]}\n    -> {c[:58]}\n' if c != n else '')
    "

---

## 11. 정제 — 동의어 클러스터링

    .venv/bin/python scripts/build_index.py --cluster 2>/dev/null | tail -30

임계값은 색인 규모가 바뀌면 다시 재야 한다. 321 건일 때 0.96, 541 건일 때 0.985.

---

## 12. 누수 차단 — 실제로 막는가

    sqlite3 -header -column data/signals.sqlite "SELECT case_id, keyword, t_peak, t_cut, label FROM trend_case;"

정답은 DB 에만 있다. 산출물에는 넣지 않는다.

    cat cases/case_pilot_rugby/meta.json

label 과 t_peak 이 없다.

    .venv/bin/python -c "
    import sys; sys.path.insert(0,'src')
    from trend_pipeline import export, storage
    conn = storage.connect()
    rows = export.fetch_before_cut(conn, '2024-08-04', ['럭비티'])
    print(f'조회 {len(rows)}행, 가장 최근 {max(r[\"observed_at\"] for r in rows)}')
    try:
        export.assert_no_leakage(list(rows) + [{'observed_at':'2099-01-01'}], '2024-08-04')
        print('통과해버림')
    except export.LeakageError as e:
        print('차단:', e)
    "

---

## 13. 인구통계 — 기준선 대비로 읽는다

분야 전체의 연령 분포. 어떤 키워드를 봐도 40 대가 최다다.

    sqlite3 -header -column data/signals.sqlite "
      SELECT entity, round(AVG(metric_value),1) avg_index
      FROM signal_raw WHERE keyword_raw='category:50000169' AND entity LIKE 'age=%'
      GROUP BY entity ORDER BY entity;"

기준선 대비 비율로 환산하면 갈린다.

    .venv/bin/python -c "
    import sys; sys.path.insert(0,'src')
    from trend_pipeline import demographics as dg, storage
    conn = storage.connect()
    for kw in ('반팔티','맨투맨','정장'):
        print(kw)
        for s in dg.profile(conn, kw, '50000169', prefix='age'): print('   ', s)
    "

---

## 14. 해외 선행 — 가설을 자료로 확인

    .venv/bin/python -c "
    import sys; sys.path.insert(0,'src')
    from trend_pipeline import features as ft, storage
    conn = storage.connect()
    for kw in ('맨투맨','후드티'):
        ll = ft.lead_lag(conn, kw, '2026-09-01', 'US', window_days=600)
        print(f'{kw}: {\"해외\" if ll.lead_days>0 else \"한국\"} 선행 {abs(ll.lead_days)}일, 상관 {ll.correlation}, 신뢰 {ll.reliable}')
    "

계획서가 전제한 방향과 반대다. 다만 계절 상품이라 계절 차이일 수 있다.

---

## 15. 후보 → 실제 상품 연결

    .venv/bin/python -c "
    import sys; sys.path.insert(0,'src')
    from trend_pipeline import features as ft, storage
    conn = storage.connect()
    for kw in ('맨투맨','후드티','럭비티'):
        ms = ft.match_products(conn, kw, limit=5)
        print(f'[{kw}] {len(ms)}건')
        for n,s,l in ms: print(f'   {s if s is None else round(s,3)}  {n[:56]}')
    " 2>/dev/null

맞는 상품이 없으면 없다고 나온다.

---

## 16. 검증 파트에 넘기는 것

    ls -la cases/case_pilot_rugby/
    head -3 cases/case_pilot_rugby/naver_shopping.csv | cut -c1-150
    wc -l cases/case_pilot_rugby/*.csv

---

## 17. 테스트

    .venv/bin/python -m pytest tests -q

---

## 18. 화면 (시간 남으면)

    bash scripts/serve.sh
