# 시연 대본

전체 15~20분. ★ 는 시간 없으면 이것만.

시작 전에 한 번:

    cd "/Users/kim_doeun/[자주프]Trend_Signal_Verification_System"
    source .env
    clear

---

# 여는 말 (30초, 명령어 없음)

> 제가 맡은 건 **후보를 찾아 검증 단계에 넘기는 데이터 파이프라인**입니다.
> 판정은 팀원이 맡고, 저는 판정에 쓸 재료를 만듭니다.
>
> 오늘은 **원본 데이터가 어떻게 생겼고, 그걸 어떻게 쓸 수 있는 형태로 바꾸는지**
> 순서대로 보여드리겠습니다.

---

# ★ 1. 원본은 이렇게 생겼습니다 (2분)

네이버에서 검색 관심도를 받아옵니다.

    curl -s -X POST "https://naverapihub.apigw.ntruss.com/search-trend/v1/search" \
      -H "X-NCP-APIGW-API-KEY-ID: $NAVER_CLIENT_ID" \
      -H "X-NCP-APIGW-API-KEY: $NAVER_CLIENT_SECRET" \
      -H "Content-Type: application/json" \
      -d '{"startDate":"2026-09-01","endDate":"2026-09-07","timeUnit":"date","keywordGroups":[{"groupName":"맨투맨","keywords":["맨투맨"]}]}' | jq

**설명**

> 맨투맨이라는 검색어의 9월 1일부터 7일까지 관심도입니다.
> 날짜마다 `ratio` 라는 숫자가 하나씩 붙어서 옵니다.
>
> 그런데 이 숫자가 검색 횟수가 아닙니다. **조회한 기간 안에서 가장 높은 날을
> 100으로 놓고 환산한 상대값**입니다.

---

# ★ 2. 그래서 같은 날인데 값이 달라집니다 (2분)

같은 9월 1일을, 조회 기간만 바꿔서 두 번 물어봅니다.

    for R in '"startDate":"2026-09-01","endDate":"2026-09-07"' '"startDate":"2026-06-01","endDate":"2026-09-07"'; do
    curl -s -X POST "https://naverapihub.apigw.ntruss.com/search-trend/v1/search" \
      -H "X-NCP-APIGW-API-KEY-ID: $NAVER_CLIENT_ID" \
      -H "X-NCP-APIGW-API-KEY: $NAVER_CLIENT_SECRET" \
      -H "Content-Type: application/json" \
      -d "{$R,\"timeUnit\":\"date\",\"keywordGroups\":[{\"groupName\":\"맨투맨\",\"keywords\":[\"맨투맨\"]}]}" \
      | jq -r '"조회기간 \(.startDate) ~ \(.endDate)   →   9/1 값: \(.results[0].data[0].ratio)"'
    done

**설명**

> 같은 9월 1일인데 값이 다르게 나옵니다. 기간을 넓히니 그 안에 더 높은 날이
> 생겨서, 9월 1일의 상대적 위치가 내려간 겁니다.
>
> 이게 왜 중요하냐면, **사례 A의 80과 사례 B의 80을 비교하면 안 된다**는 뜻입니다.
> 저희는 과거 사례를 여러 개 놓고 비교하는 실험을 하니까 직접 영향을 받습니다.
>
> 그래서 사례끼리 비교할 때는 값 자체가 아니라 **변화율이나 기울기처럼
> 크기와 무관한 지표로만** 비교하도록 설계했습니다.

---

# ★ 3. 커머스 쪽 원본 (1분)

29CM 랭킹입니다.

    curl -s -A "TrendSignalResearchBot/0.1" -H "Referer: https://www.29cm.co.kr/" \
      "https://recommend-api.29cm.co.kr/api/v4/best/items?categoryList=272103100&periodSort=ONE_DAY&limit=10&offset=0" \
      | jq -r '.data.content[] | "\(.itemName)\t\(.frontBrandNameKor)\t리뷰\(.reviewCount)\t좋아요\(.heartCount)\t품절\(.isSoldOut)"' | column -t -s$'\t'

**설명**

> 원래는 무신사를 쓰려고 했는데, 무신사는 수집 규칙상 접근이 막혀 있어서
> 29CM로 대체했습니다.
>
> 순위 말고도 **리뷰 수**를 같이 받습니다. 순위는 광고나 프로모션으로 올릴 수
> 있지만, 리뷰는 실제로 사야 쌓입니다. 그래서 "순위는 올랐는데 리뷰가 안 늘었다"를
> 광고 효과를 의심하는 근거로 씁니다.

---

# ★ 4. 원본은 지저분합니다 (1분)

수집된 상품 이름을 그대로 봅니다.

    sqlite3 data/signals.sqlite "SELECT DISTINCT keyword_raw FROM signal_raw WHERE channel='commerce_rank' ORDER BY RANDOM() LIMIT 25;"

**설명**

> 상품 이름에 프로모션 문구, 배송 차수, 품번, 색상이 전부 섞여 있습니다.
> `[29CM 단독]`, `2차 9/11 순차배송`, `TG3-TS09` 같은 것들입니다.
>
> 이대로 두면 문제가 생깁니다. 같은 상품의 색상 다른 버전이 서로 다른
> 상품으로 세어지고, 반대로 `[29CM 단독]` 이 붙었다는 공통점만으로
> 전혀 다른 상품끼리 묶이기도 합니다.

---

# ★ 5. 그래서 정제합니다 (2분)

    .venv/bin/python -c "
    import sys; sys.path.insert(0,'src')
    from trend_pipeline import embeddings as e, storage
    for (n,) in storage.connect().execute(\"SELECT DISTINCT keyword_raw FROM signal_raw WHERE channel='commerce_rank' ORDER BY RANDOM() LIMIT 15\"):
        c = e.normalize_for_embedding(n)
        if c != n: print(f'{n[:56]}\n     →  {c[:56]}\n')
    " 2>/dev/null

**설명**

> 상품이 무엇인지와 관계없는 부분을 걷어냅니다.
> 괄호, 대괄호, 배송 차수, 품번, 끝에 붙은 색상 이름을 지웁니다.
>
> 원본은 그대로 보관하고, **비교할 때만 이 정제된 이름을 씁니다.**
> 나중에 되돌려서 확인할 수 있어야 하니까요.

---

# 6. 정제하면 흩어진 게 하나로 묶입니다 (2분)

    .venv/bin/python scripts/build_index.py --cluster 2>/dev/null | tail -25

**설명**

> 이름이 달라도 의미가 가까우면 하나로 묶습니다.
> `LAUNDRY SHIRT` 의 색상 9가지가 한 덩어리가 된 걸 보실 수 있습니다.
>
> 글자 비교로는 안 됩니다. `Raglan` 과 `래글런` 은 글자가 하나도 안 겹치니까요.
> 그래서 문장을 숫자 벡터로 바꿔서 의미가 가까운지를 봅니다.
>
> 얼마나 가까워야 같은 걸로 볼지는 실제 데이터로 맞췄습니다. 처음엔 321건일 때
> 기준을 정했는데, 541건으로 늘자 다른 품목이 섞이기 시작해서 다시 조정했습니다.
> **한 번 정하고 끝나는 값이 아니라는 걸 확인한 셈입니다.**

---

# ★ 7. 4개 채널을 한 테이블에 모읍니다 (2분)

    sqlite3 -header -column data/signals.sqlite "
      SELECT channel, COUNT(*) rows, COUNT(DISTINCT keyword_raw) keywords,
             MIN(substr(observed_at,1,10)) first, MAX(substr(observed_at,1,10)) last
      FROM signal_raw GROUP BY channel;"

**설명**

> 네 군데서 모읍니다. 네이버 검색, 네이버 쇼핑, 구글 트렌드, 29CM 랭킹입니다.
> 형식도 주기도 다 다르지만 **저장은 하나로 통일**했습니다.
>
> 계획서에 "여러 독립 채널에서 같은 변화가 보이는지 교차검증한다"는 원칙이
> 있는데, 그러려면 채널이 여러 개여야 하고 같은 방식으로 비교 가능해야 합니다.

---

# ★ 8. 시점을 두 개로 나눴습니다 (2분)

    sqlite3 -header -column data/signals.sqlite "
      SELECT substr(observed_at,1,10) 관측시점, substr(collected_at,1,10) 수집시점,
             channel, keyword_raw, round(metric_value,1) 값
      FROM signal_raw WHERE channel='naver_datalab' AND observed_at < '2022-01-01' LIMIT 5;"

**설명**

> 왼쪽이 **그 데이터가 가리키는 날짜**, 오른쪽이 **저희가 가져온 날짜**입니다.
> 2021년 데이터를 2026년에 받아온 겁니다.
>
> 저희 연구는 "과거 어느 시점에 알 수 있었던 정보만으로 판단이 가능했는가"를
> 재현하는 거라, 이 둘을 반드시 구분해야 합니다.
>
> 원래 계획서에는 시점 컬럼이 하나였는데, 그러면 이 행들이 전부 "오늘 관측"으로
> 기록됩니다. 그럼 **과거 시점 기준으로 자르는 필터가 아무것도 못 거릅니다.**
> 설계를 바꾼 부분입니다.

---

# ★ 9. 미래 데이터가 새는 걸 실제로 막습니다 (2분)

    .venv/bin/python -c "
    import sys; sys.path.insert(0,'src')
    from trend_pipeline import export, storage
    conn = storage.connect()
    rows = export.fetch_before_cut(conn, '2024-08-04', ['럭비티'])
    print(f'판단 기준일 이전 자료만 조회 → {len(rows)}행, 가장 최근 {max(r[\"observed_at\"] for r in rows)}')
    print('이제 일부러 2099년 데이터를 섞어서 통과시켜 봅니다...')
    try:
        export.assert_no_leakage(list(rows) + [{'observed_at':'2099-01-01'}], '2024-08-04')
        print('통과해버림 — 검증기가 동작하지 않음')
    except export.LeakageError as e:
        print('차단됨:', e)
    "

**설명**

> 과거 사례를 재현하는 실험이라, **판단 시점 이후의 데이터가 한 건이라도 섞이면
> 실험 전체가 무의미해집니다.** 답을 보고 문제를 푸는 셈이니까요.
>
> 그래서 세 군데서 막습니다. 수집할 때, 계산할 때, 그리고 파일로 내보내기
> 직전에 한 번 더 봅니다. 지금 보신 게 마지막 관문입니다.
>
> 일부러 2099년 데이터를 넣어봤더니 거부하고 전체를 중단시킵니다.

---

# 10. 사람 통계는 그대로 읽으면 안 됩니다 (2분)

    sqlite3 -header -column data/signals.sqlite "
      SELECT entity 연령대, round(AVG(metric_value),1) 평균지수
      FROM signal_raw WHERE keyword_raw='category:50000169' AND entity LIKE 'age=%'
      GROUP BY entity ORDER BY entity;"

**설명 (여기까지 먼저)**

> 티셔츠 분야 전체의 연령 분포입니다. 40대가 제일 많습니다.
> 그런데 **어떤 키워드를 조회해도 40대가 제일 많이 나옵니다.**
> 네이버쇼핑을 쓰는 사람들이 그런 거지, 그 상품의 특징이 아닙니다.

이어서

    .venv/bin/python -c "
    import sys; sys.path.insert(0,'src')
    from trend_pipeline import demographics as dg, storage
    conn = storage.connect()
    for kw in ('반팔티','맨투맨','정장'):
        sk = dg.profile(conn, kw, '50000169', prefix='age')
        t = next(s for s in sk if s.group=='20')
        print(f'{kw:<5} 20대 배율 {t.lift:>5.2f}   (1.0이면 분야 평균과 같음)')
    "

**설명**

> 그래서 분야 전체를 기준선으로 놓고 **그 대비 몇 배인지**로 바꿨습니다.
>
> 반팔티는 0.83, 거의 평균입니다. 여름에 다들 사니까요.
> 정장은 2.78, 20대가 세 배 가까이 많습니다. 신입사원 정장 수요로 보입니다.
>
> 이렇게 바꿔야 "이 상품이 특정 연령에 쏠렸나"를 판단할 수 있습니다.

---

# 11. 가설을 데이터로 확인했습니다 (2분)

    .venv/bin/python -c "
    import sys; sys.path.insert(0,'src')
    from trend_pipeline import features as ft, storage
    conn = storage.connect()
    for kw in ('맨투맨','후드티'):
        ll = ft.lead_lag(conn, kw, '2026-09-01', 'US', window_days=600)
        print(f'{kw:<5} {\"해외\" if ll.lead_days>0 else \"한국\"}가 {abs(ll.lead_days)}일 먼저   (상관 {ll.correlation})')
    "

**설명**

> 계획서에 "유행은 해외에서 한국으로 넘어온다"는 가설이 있었습니다.
> 실제로 확인해봤더니 **반대로 나왔습니다.** 한국이 3주에서 5주 먼저입니다.
>
> 다만 이걸로 가설이 틀렸다고 결론 내리진 않았습니다. 맨투맨과 후드티는
> 계절 상품이라, 한국과 미국의 **계절이 오는 시점 차이**일 수도 있습니다.
>
> 이런 건 그대로 기록해두고 나중에 계절 요인을 걷어낸 뒤 다시 봅니다.

---

# 12. 검증 파트에 이걸 넘깁니다 (1분)

    ls -la cases/case_pilot_rugby/
    cat cases/case_pilot_rugby/meta.json

**설명**

> 사례 하나를 폴더로 묶어서 넘깁니다. 채널별 데이터와 설명 파일입니다.
>
> 중요한 건 **정답이 여기 없다는 것**입니다. 이게 실제로 유행한 상품인지,
> 언제 터졌는지는 저만 갖고 있고 안 넘깁니다.
> 정답을 보면서 판단하면 검증이 아니니까요.

---

# ★ 13. 원하시는 걸 바로 조회해 보겠습니다 (2분)

    sqlite3 data/signals.sqlite

들어간 뒤 예를 들면

    SELECT keyword_raw,
           MIN(CASE WHEN observed_at LIKE '2026-09-27%' THEN metric_value END) AS 이전,
           MIN(CASE WHEN observed_at LIKE '2026-09-29%' THEN metric_value END) AS 이후
    FROM signal_raw WHERE channel='commerce_rank' AND metric_type='rank'
    GROUP BY keyword_raw
    HAVING 이전 IS NOT NULL AND 이후 IS NOT NULL AND 이전 - 이후 > 20
    ORDER BY 이전 - 이후 DESC LIMIT 10;

나올 때는 `.quit`

**설명**

> 이틀 사이에 순위가 20계단 넘게 오른 상품들입니다.
>
> 데이터가 전부 이 안에 들어 있어서, 궁금하신 게 있으면 바로 조회해서
> 보여드릴 수 있습니다.

> 조회할 때 쓸 수 있는 값은 `DEMO_reference.md` 4번 절에 정리해 뒀습니다.

---

# 닫는 말 (30초)

> 지금까지가 **재료를 만드는 부분**입니다. 4개 채널에서 3만 건 넘게 모았고,
> 정제와 검증 장치가 동작합니다.
>
> 다음은 **과거 사례를 골라서 실제로 돌려보는 것**인데, 어떤 사례를 고를지
> 기준을 먼저 정해야 합니다. 이건 팀원과 같이 정해야 하는 부분이라
> 아직 못 넘어가고 있습니다.

---

# 예상 질문

**Q. 무신사를 왜 안 쓰나요**
> 무신사는 수집 규칙상 접근이 막혀 있습니다. 29CM로 대체했는데, 29CM가
> 무신사 계열사라 상품 구성이 비슷합니다. 다만 계열사라서 **독립된 채널
> 두 개로 세지는 않습니다.** 정식 허가를 받으면 바로 붙일 수 있게 만들어 뒀습니다.

**Q. 데이터가 며칠치밖에 없는 것 같은데**
> 29CM는 크롤링이라 과거를 못 가져옵니다. 그래서 두 갈래로 나눴습니다.
> **과거 사례 재현은 과거 조회가 되는 네이버·구글**로 하고,
> 29CM는 지금부터 쌓아서 나중에 실제 적용을 보여주는 용도입니다.

**Q. 정확도가 얼마나 되나요**
> 정확도를 목표로 잡지 않았습니다. 사례를 저희가 고르기 때문에 쉬운 것만
> 고르면 정확도는 얼마든지 올릴 수 있습니다. 대신 **판단 근거가 남는지,
> 반대 증거를 찾았는지**를 기준으로 삼고 있습니다.

**Q. 이건 어떻게 나온 숫자인가요**
> (13번으로 가서 그 자리에서 조회)
