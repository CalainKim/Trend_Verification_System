# 트렌드 시그널 검증 시스템 - 데이터 수집 파이프라인

2026-2학기 자기주도프로젝트 (아주대 소프트웨어, 산업체 연계: 무신사)
담당 범위: 시그널 후보 수집, 정제, 정규화, 특징 추출

확정/보류/기각 판정은 팀원 담당이며 이 저장소의 범위가 아니다.
이 저장소는 검증 단계에 넘길 입력값을 만드는 데까지만 책임진다.


## 검증 파트는 여기서 시작한다

순서대로 넷만 보면 된다.

    1. docs/verification-handoff.md      무엇을 받고 무엇을 만드나
    2. benchmark/cases/                  문제지 139건. 바로 읽힌다
    3. verification/examples/            판정 출력 예시 3건과 읽는 법
    4. benchmark-index-long/LABELS.md    혼자 채점하며 반복하는 방법

문제지가 셋이고 역할이 다르다.

    benchmark-index-long/   352건   공개   혼자 채점하며 반복한다
    benchmark/              139건   봉인   최종 숫자를 여기서 낸다
    benchmark-index/        207건   봉인   둘째 도메인

공개 쪽은 정답이 저장소에 있어 바로 채점된다.

    python scripts/score_verdicts.py --benchmark benchmark-index-long \
        --verdicts <판정 경로>

봉인 쪽은 정답이 없다. 판정을 묶어서 수집 파트에 넘기면 채점해 돌려준다.
볼 때마다 홀드아웃이 닳으므로 횟수를 기록한다.

    python scripts/score_verdicts.py --verdicts <판정 경로> --pack verdicts.json

API 키가 없어도 문제지는 다 읽힌다. 수집을 직접 돌릴 때만 키가 필요하다.


## 1. 아키텍처

두 개의 트랙으로 구성한다.

```
데이터 소스

  트랙 A 역추적 (메인)  ─ 과거 구간 소급 조회가 되는 API만 쓴다
      네이버 데이터랩 검색어 트렌드   국내 관심도 (메인 지표)
      네이버 쇼핑인사이트             성별과 연령 분해
      Google Trends                  해외 선행 여부
      뉴스 아카이브                   캠페인 시점 (반증 근거)

  트랙 B 실시간 축적 (보조)  ─ 크롤링, 소급 수집 불가
      29CM 베스트 랭킹   순위, 리뷰 수, 좋아요 수, 품절 여부
      매일 쌓지 않으면 그날치는 영구 손실
  │
  ▼
collectors/   소스별 수집 모듈
  │   형식, 주기, 노이즈 특성이 달라 모듈은 나누고
  │   반환값만 공통 RawRecord 로 통일한다
  ▼
RawRecord     시점을 두 개로 나눠 들고 있다
  │   observed_at   지표가 가리키는 시점   ← 누수 차단의 기준
  │   collected_at  우리가 가져온 시점
  ▼
data/snapshots/{channel}/{날짜}.csv        수집 원본 (커밋 대상)
  │   소급 수집이 안 되므로 텍스트로도 보존한다
  ▼
SQLite  signal_raw                        재구성 가능한 파생물
  │   수집 실행 하나가 곧 스냅샷 하나
  │
  ├──▶ analytics.py  ─ 결측일, 순위 변화, 반증 신호
  │      └──▶ report.py (터미널), build_dashboard.py (대시보드)
  │
  ▼
정제와 정규화                              (미구현)
  │   동의어와 유사 표현을 하나의 후보로 묶는다
  ▼
특징 추출  candidate_summary               (미구현)
  │   독립 채널 2개 이상에서 잡힌 후보만 통과시킨다
  ▼
┌─ T_cut 누수 차단 관문
│  observed_at < T_cut 을 내보내기 직전 재검증
└─ 한 건이라도 위반하면 생성 전체를 중단한다
  │
  ▼
cases/{case_id}/
      채널별 CSV    T_cut 이전 관측치만
      meta.json     정답 라벨과 T_peak 은 뺀다 (블라인드)
  │
──│──────────────────────────── 이 저장소의 범위는 여기까지
  ▼
검증 단계 (팀원 담당)   확정 / 보류 / 기각
```

트랙 A (역추적, 메인)
  과거에 실제로 발생한 트렌드를 정답으로 두고, 그 시점 이전 데이터만으로
  사전 포착이 가능했는지를 재현한다. 실시간 수집만으로는 16주 안에 검증할
  트렌드가 발생한다는 보장이 없어 이쪽을 메인으로 둔다.
  과거 시점 소급 조회가 가능한 API만 사용한다.

트랙 B (실시간 축적, 보조)
  커머스 랭킹을 일 단위로 수집해 쌓아둔다. 크롤링은 소급 수집이 불가능하므로
  가능한 한 이른 시점부터 수집을 시작한다. 초반에는 분석하지 않고 축적만 하고,
  후반부에 트랙 A로 확립한 검증 기준을 실제 데이터에 적용해 시연하는 데 쓴다.


## 2. 데이터 소스

```
트랙 A
  네이버 데이터랩 검색어 트렌드 API   국내 관심도 일별 추이 (메인 지표)
  네이버 쇼핑인사이트 API             카테고리/키워드 클릭 추이, 성별과 연령 분해
                                      2016-01-01 부터 조회 가능 (실측 확인)
                                      성별과 연령 교차 조건 지원 (20대 남성 등)
  Google Trends                       해외 선행 여부 검증
                                      pytrends 사용. 첫 요청이 자주 429 라 재시도 필요
                                      한국어 키워드는 해외 검색량이 0이므로 대응 영문어 필요
  뉴스 아카이브                       캠페인과 미디어 노출 시점 확인 (반증 근거)

트랙 B
  29CM 베스트 랭킹 API                순위, 리뷰 수, 좋아요 수, 품절 여부
                                      GitHub Actions 에서는 403. 로컬에서 수집한다
  코오롱몰 베스트                      순위, 좋아요 수, 자사 브랜드 여부, 시즌
                                      2026-11-05 부터. 탭 4개 x 100건
  하이버 실시간 랭킹                   순위, 순위 점수, 브랜드(42%)
                                      2026-11-05 부터. 50건
```

커머스를 셋으로 늘린 이야기는 `docs/commerce-channels.md` 에 있다. 29CM 만
있던 동안 커머스는 사실상 한 채널이었다. 교차 채널 확인의 근거가 거기서
생긴다.

네이버 데이터랩 API 는 developers.naver.com 이 아니라 네이버 클라우드 플랫폼의
NAVER API HUB 를 통해 제공된다. 호스트는 naverapihub.apigw.ntruss.com 이고 인증
헤더는 X-NCP-APIGW-API-KEY-ID / X-NCP-APIGW-API-KEY 다. 예전 방식(openapi.naver.com
+ X-Naver-Client-*)으로 부르면 키가 멀쩡해도 401 이 난다. 엔드포인트 경로는 문서에
전부 나와 있지 않아 실제 호출로 확인했다.

네이버 데이터랩 두 API 는 절대량이 아니라 요청 안에서 정규화된 상대 지수를 돌려준다.
조회 구간의 최댓값이 100 이 되도록 스케일된 값이라, 요청이 다르면 값을 직접 비교할 수
없다. 서로 다른 케이스의 지수를 그대로 비교하면 잘못된 결론이 나온다. 비교가 필요하면
같은 요청 안에 함께 넣거나, 변화율과 기울기처럼 스케일에 영향받지 않는 형태로 바꿔 쓴다.

무신사 랭킹은 robots.txt가 화이트리스트 방식이라 자체 수집기를 전면 차단한다.
수집 허가가 나오기 전까지는 29CM를 대체 소스로 쓴다. docs/robots-compliance.md 참고.

29CM는 무신사 계열 서비스다(로그인 SSO와 주문 서비스 일부를 공유한다).
따라서 무신사와 29CM를 서로 독립적인 두 채널로 세면 안 된다. 교차검증에서는
같은 커머스 채널로 묶고, 독립 채널은 검색/쇼핑인사이트 쪽에서 확보한다.

코오롱몰과 하이버는 운영사가 달라서 독립 채널로 센다. 단 하이버는 브랜디가
운영하므로(이미지 호스트가 image.brandi.co.kr 이다) 브랜디를 나중에 붙이면
하이버와 같은 채널로 묶어야 한다.


## 3. 파이프라인

```
  수집        소스별 수집 모듈이 각자의 형식을 읽어 공통 RawRecord로 반환한다.
              모듈은 분리하되 저장 형식은 하나로 통일한다.

  적재        storage.insert_raw()가 SQLite signal_raw 테이블에 넣는다.
              UNIQUE(channel, keyword_raw, entity, metric_type, observed_at)로
              중복을 막으므로 같은 날 여러 번 실행해도 결과가 같다.

  스냅샷      관측일별 CSV를 data/snapshots/{channel}/{YYYY-MM-DD}.csv에 남긴다.
              크롤링 데이터는 소급 수집이 불가능하므로 원본을 텍스트로도 보존한다.
              SQLite는 이 스냅샷으로부터 언제든 재구성 가능한 파생물로 취급한다.
              하루 파일 안에 그날의 스냅샷이 여러 개 들어갈 수 있다.

  정제        결측/중복/이상치 처리. 동의어 및 유사 표현은 임베딩 기반 유사도로
              묶어 하나의 후보로 통합한다. sqlite-vec 벡터 검색을 쓴다.

  특징 추출   후보별로 채널별 변화 추이, 채널 간 시차, 캠페인과의 시간적 연관성,
              성별과 연령 분포, 클릭 대비 전환 지표를 요약한다. (미구현)

  내보내기    export.write_case_bundle()이 케이스 폴더를 만든다.
```


## 4. 시점 처리

시점 컬럼을 두 개로 나눈다.

```
  observed_at    지표가 실제로 가리키는 시점. 누수 차단의 기준.
  collected_at   그 값을 가져온 시점. 재현성과 감사 용도.
```

네이버 데이터랩처럼 과거 구간을 소급 조회하는 API는 오늘 호출해도 observed_at이
과거다. 두 값을 한 컬럼으로 합치면 모든 행이 오늘 관측으로 보여 T_cut 필터가
성립하지 않는다. 그래서 분리했다.

랭킹 수집은 실행 한 번이 곧 스냅샷 하나이고, observed_at에 초 단위까지 기록한다.
날짜만 기록하면 하루 두 번 수집할 때 두 실행이 같은 키로 충돌한다. UNIQUE 제약이
1차 실행값을 지키는 사이 그동안 랭킹에 새로 진입한 상품만 통과해서, 한 날짜 안에
서로 다른 시점의 순위가 섞이고 같은 순위가 두 번 나타난다. 부분 실패한 실행이
그날 데이터를 영구히 오염시키는 경로이기도 하다. 실행마다 스냅샷을 분리하면
하루 두 번 수집이 중복이 아니라 이중화가 된다.

일 단위 분석은 storage.daily_snapshots()로 그날의 스냅샷 하나를 골라 쓴다.
서로 다른 실행을 섞으면 안 된다.

순위는 (상품, 랭킹 목록)의 속성이라 entity에 랭킹 목록 코드를 함께 넣는다.
유니섹스 상품은 여성과 남성 랭킹에 동시에 오르므로 이렇게 하지 않으면 한 쪽이
유실된다. 리뷰 수와 좋아요 수는 상품 자체의 속성이라 상품 단위로 한 번만 저장한다.

누수 차단은 두 번 한다. 수집 단계에서 거르는 것과 별개로,
export.write_case_bundle()이 파일을 쓰기 직전 assert_no_leakage()로
observed_at < T_cut을 재검증한다. 한 건이라도 위반하면 번들 생성 전체가 중단된다.

케이스 번들의 meta.json에는 label과 T_peak을 쓰지 않는다. 정답은 수집 담당자만
trend_case 테이블에 보관하고, 검증팀에 전달되는 폴더는 블라인드 상태로 둔다.
정답을 보고 끼워맞추는 것을 막기 위함이다.


## 5. 벡터 검색

두 가지 용도로 쓴다.

첫째, 동의어와 유사 표현을 하나의 후보로 묶는다. '발라클라바'와 'balaclava' 가
흩어져 있으면 각각은 신호가 약해 보여서 진짜 시그널을 놓친다.

둘째, 확정된 후보를 실제로 수집한 아이템으로 되돌린다. 검증 단계가 어떤 후보를
확정하더라도 그것이 우리가 수집한 어떤 상품을 가리키는지 연결되지 않으면
결과를 쓸 수 없다.

SQLite 에 sqlite-vec 확장을 얹는다. 별도 DB 를 쓰지 않으므로 기존 수집 데이터와
같은 파일에 들어가고, 스냅샷에서 재구성해도 둘이 어긋나지 않는다.

클러스터링 임계값은 연구 결과를 좌우하는 값이다. 낮추면 서로 다른 상품이 한
후보로 뭉치고 높이면 같은 것이 갈라진다. 코드의 기본값은 출발점일 뿐이고,
실제 데이터로 확인해 조정한 근거를 남겨야 한다.

## 6. 저장 스키마

```
signal_raw            원시 수집 데이터. 모든 채널이 공유한다.
signal_candidate      동의어 클러스터링 결과. 흩어진 표현을 하나의 후보로 묶은 것.
candidate_keyword_map 후보와 원시 레코드의 연결.
candidate_summary     후보별 채널 요약. 검증 단계로 넘어가는 입력값.
trend_case            역추적 케이스의 정답. 산출물로 내보내지 않는다.
```

정의는 src/trend_pipeline/schema.sql에 있다.


## 7. 디렉터리 구조

```
  src/trend_pipeline/
    models.py            RawRecord. 모든 소스가 공유하는 단일 레코드 표현
    schema.sql           SQLite 스키마
    storage.py           저장 레이어
    snapshots.py         일별 CSV 스냅샷 입출력
    export.py            케이스 번들 생성, 누수 차단
    config.py            .env 로딩, API 키 확인
    collectors/
      base.py            수집기 공통 인터페이스, 요청 간격 제어
      cm29_rank.py       29CM 베스트 랭킹 수집기
      naver_base.py      네이버 오픈 API 공통 계층
      naver_datalab.py   검색어 트렌드 수집기
      naver_shopping.py  쇼핑인사이트 수집기 (성별과 연령 분해)
      gtrends.py         Google Trends 수집기 (지역별 관심도)
    analytics.py         수집 데이터 요약 집계 (리포트와 대시보드가 공유)
    demographics.py      인구통계 쏠림 (분야 기준선 대비 리프트)
    features.py          후보별 특징 추출 (as_of 이전 자료만)
    persistence.py       지속성 케이스 생성 (상승이 버티는지)
    scoring.py           판정 채점 (기저율 대비, 기권 처리)
    webtheme.py          대시보드 공통 테마
    embeddings.py        텍스트 임베딩 (로컬 다국어 모델)
    vectorstore.py       sqlite-vec 벡터 색인 및 유사도 검색
    clustering.py        동의어와 유사 표현 클러스터링
  scripts/
    collect_daily.py     트랙 B 일별 수집 진입점
    load_snapshots.py    스냅샷으로부터 DB 재구성
    report.py            터미널 리포트
    build_dashboard.py   docs/index.html 생성
    verify_naver_key.py  API 키 확인 및 실제 제약 실측
    build_index.py       벡터 색인 생성, 동의어 클러스터링
    search_items.py      수집 아이템 유사도 검색
    build_case.py        역추적 케이스 번들 생성
    extract_attributes.py    상품명에서 속성 키워드 추출
    collect_gtrends.py       구글 트렌드 수집 (지역별 질의어)
    collect_gtrends_hourly.sh    시간별 증분 수집 (launchd 가 호출)
    install_gtrends_schedule.sh  시간별 수집 등록
    build_persistence_cases.py   지속성 케이스와 기저율 생성
    build_all_benchmarks.sh      벤치마크 셋을 한 번에 생성
    score_verdicts.py            판정 채점과 성적표
    build_case_dashboard.py  케이스 분석 화면 생성
    serve.sh             대시보드를 로컬에서 띄운다
    collect_and_push.sh  로컬 일일 수집 (launchd 가 호출)
    install_local_schedule.sh  일일 수집 등록
  data/snapshots/        수집 원본 CSV (커밋 대상)
  data/attributes.yml    속성 키워드 사전 (사람이 검수한다)
  cases/                 역추적 케이스 산출물 (검증팀 전달용)
  benchmark/             커머스 지속성 벤치마크 (정답은 저장소에 없다)
  benchmark-index/       검색 지수 벤치마크 (한국, 확인 28일)
  benchmark-index-long/  검색 지수 벤치마크 (3개 지역, 확인 84일)
  verification/          검증 파트 인터페이스 (판정 결과 스키마)
    examples/            판정 출력 실제 예시 3건과 읽는 법
  docs/                  GitHub Pages 대시보드와 근거 문서
                         verification-handoff.md 는 검증 파트 인수인계 문서
  tests/                 저장 및 누수 차단 계약 테스트
```


## 7-1. 지속성 벤치마크

이 저장소의 주 산출물이다. 트렌드를 맞히는 것이 아니라 **맞히는 모델을
채점하는 시험지**다.

### 묻는 것

원인은 외부에서 관측할 수 없다. 광고 집행과 노출 알고리즘은 쇼핑몰 안에만
있다. 그래서 "왜 올랐나" 대신 **"얼마나 버티나"** 를 묻는다. 광고로 올린
순위는 광고가 끝나면 떨어지고 그 떨어짐은 밖에서도 보인다. 질문을 바꾸면
관측 불가능한 문제가 관측 가능한 문제가 된다.

정답은 사람이 정하지 않는다. 관측 구간에서 오른 것을 찾고, 확인 구간에서
상승분의 절반이 남았는지를 자료가 답한다. 그래서 케이스가 자동으로 쌓인다.

### 셋으로 나눈다

    benchmark/              29CM 순위     확인  7일   61건   기저율 54.1%
    benchmark-index/        검색 한국     확인 28일   23건   기저율 73.9%
    benchmark-index-long/   검색 3개 지역  확인 84일   53건   기저율 47.2%

기저율이 47% 에서 74% 까지 벌어진다. 지표의 성질과 확인 기간이 다르기
때문이다. **셋을 합쳐 하나의 점수로 내면 안 된다.**

### 채점

    ./scripts/build_all_benchmarks.sh                       # 셋을 다시 만든다
    python scripts/score_verdicts.py --benchmark benchmark --baselines
    python scripts/score_verdicts.py --benchmark benchmark --verdicts <경로>

정확도만 보고하면 찍은 것과 같은 점수를 성과로 읽는다. 전부 "지속" 이라고
찍으면 기저율이 그대로 나오므로 항상 함께 낸다. 유의성은 정확도 신뢰구간의
아래끝이 기저율을 넘는지로 본다.

보류는 오답이 아니라 답하지 않은 것이다. 오답으로 세면 신중한 판정이 벌을
받고, 채점에서 빼기만 하면 쉬운 것만 골라 답한 판정이 상을 받는다. 그래서
커버리지와 정확도를 함께 내고 기저율도 답한 부분집합에서 다시 계산한다.

### 정답은 저장소에 없다

공개 저장소라 검증 파트가 정답을 보면 블라인드가 깨진다. labels.sealed.json
은 제외하고 봉인 해시만 둔다. 채점이 끝난 뒤 정답을 고치지 않았음을 해시로
확인한다.

### 지금은 표본이 모자란다

키워드가 9개뿐이라 +20%p 개선만 가려낼 수 있다. 사전에 74개가 있고 전부
수집하면 주 벤치마크가 190건쯤 되어 +10%p 를 주장할 수 있다. 구글 트렌드는
연속 24회쯤에서 IP 단위로 막히므로 시간별 증분 수집으로 모은다.

    bash scripts/install_gtrends_schedule.sh    # 매시 17분 실행 등록
    tail -f data/gtrends.log


## 8. 기술 스택

```
  Python 3.12
  requests          HTTP 수집
  pandas            데이터 처리
  beautifulsoup4    HTML 파싱
  SQLite            저장 (표준 라이브러리 sqlite3)
  sqlite-vec        벡터 검색 확장
  sentence-transformers  로컬 임베딩 (intfloat/multilingual-e5-base)
  pytest            테스트
  GitHub Actions    일 2회 자동 수집 (KST 09:00, 21:00)
```

임베딩은 로컬에서 돌린다. API 키도 비용도 없고 오프라인에서 재현되므로
지도교수와 팀원이 같은 코드로 같은 결과를 얻을 수 있다. 상품명이 한영 혼용이라
한국어 전용 모델이 아니라 다국어 모델을 쓴다.

벡터 색인은 일별 자동 수집에 넣지 않는다. 모델이 1GB 를 넘어 매일 내려받으면
낭비이고, 색인은 수집만큼 자주 갱신할 필요가 없다. 필요할 때 로컬에서 만든다.


## 9. 실행

```
  python3.12 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  cp .env.example .env          네이버 API 키 입력

  python scripts/collect_daily.py             상의 카테고리 일간 랭킹 100위 수집
  python scripts/collect_daily.py --status    누적 현황 출력
  python scripts/load_snapshots.py            스냅샷으로부터 DB 재구성
  python scripts/export_snapshots.py          DB 를 스냅샷 CSV 로 내보내기
  python scripts/report.py                    터미널 리포트
  bash scripts/serve.sh                       대시보드를 브라우저로 열기
  python scripts/build_dashboard.py           수집 현황 화면 생성
  python scripts/build_case_dashboard.py      케이스 분석 화면 생성
  python scripts/verify_naver_key.py          네이버 키 확인
  python scripts/build_index.py --cluster     벡터 색인 + 동의어 클러스터링
  python scripts/search_items.py "발라클라바"   유사 아이템 검색
  python -m pytest tests -q                   테스트
```


## 9-1. 다른 컴퓨터에서 이어서 작업하기

DB 는 저장소에 올리지 않는다. 90MB 짜리 바이너리라서 수집할 때마다 전체가
다시 저장되고 git 이 변경분을 추려내지 못한다. 대신 `data/snapshots` 의 CSV 가
원본이고 DB 는 거기서 다시 만드는 파생물이다.

```
  git clone https://github.com/CalainKim/Trend_Verification_System
  cd Trend_Verification_System
  python3.12 -m venv .venv && source .venv/bin/activate
  pip install -r requirements.txt

  python scripts/load_snapshots.py      CSV 에서 DB 복원 (127,667행, 2초)
  ./scripts/build_all_benchmarks.sh      벤치마크 세 종 재생성
```

복원이 제대로 됐는지는 봉인 해시로 확인한다. 재생성한
`<벤치마크>/labels.digest.txt` 가 저장소에 들어 있는 값과 같으면 같은 자료로
같은 문제지가 만들어진 것이다. 2026-11-02 에 빈 디렉터리로 clone 해서 확인한
값은 아래와 같다.

    benchmark              61건    9cef9adadd3a4b3c
    benchmark-index       207건    3d876642a5b0d03a
    benchmark-index-long  352건    74ae744852957960

정답 파일 자체는 저장소에 없고 해시만 들어 있다. 받는 쪽에서 다시 만들어도
같은 해시가 나오는 것이 정답이 자료에서 기계적으로 나온다는 증거다.

경로에 대괄호가 들어 있으면 pytest 가 돈다. 저장소를 `[자주프]` 같은 이름의
디렉터리 안에 두면 테스트 ID 파싱이 실패하므로 clone 위치를 그렇게 잡지 않는다.

### 스냅샷이 자동으로 쌓이는 구조

수집기는 DB 에 넣는 즉시 같은 내용을 CSV 로도 쓴다. 한 속성을 받을 때마다
쓰므로 중간에 구글 트렌드 한도에 걸려 끝나도 받은 만큼은 텍스트로 남는다.
`scripts/collect_and_push.sh` 가 10시와 22시에 `data/snapshots` 를 커밋하고
푸시하므로, 수집한 자료는 하루 두 번 저장소로 넘어간다.

채널마다 파일을 쪼개는 단위가 다르다.

    채널              단위      파일      이유
    commerce_rank    관측일    36개      그 시점의 순위만 주므로 하루가 한 파일
    gtrends          연도       6개      한 번 요청에 5년치가 와서 하루로 쪼개면 253개
    naver_datalab    연도       4개      같은 이유. 하루로 쪼개면 네 줄짜리 1,095개
    naver_shopping   연도       5개      같은 이유

CSV 42MB 가 압축되면 1.7MB 다. metadata 열의 JSON 이 행마다 거의 같아서
20:1 에서 35:1 까지 줄어든다.


## 9-2. 보여 줄 파일 만들기

검증 파트나 지도교수께 보일 때는 파일 하나로 만든다. 받는 쪽은 더블클릭만
하면 된다. 서버도, 설치도, 로그인도, 네트워크도 필요 없다.

```
  ./scripts/build_viewer.sh                최신 주
  ./scripts/build_viewer.sh 2026-11-01     주 지정
```

결과는 `build/트렌드 모니터 (날짜).html` 이고 3.0MB 다. 2.0MB 가 Pretendard
폰트인데, 안에 넣어야 받는 쪽에서 글꼴이 깨지지 않는다.

재료가 전부 저장소에 있으므로 clone 만 하면 어디서든 다시 만들 수 있다.

    design/Trend Monitor v8.dc.html   화면 원본 사본
    design/runtime/                   화면을 돌리는 부품과 폰트
    build/frontend_data.js            수집분에서 만든 데이터

화면을 고치는 자리는 Claude Design 이다. 거기서 새로 다듬었으면 `design/` 의
사본을 바꾸고 스크립트를 다시 돌린다. 스크립트가 고칠 자리를 못 찾으면 즉시
멈추므로, 구조가 바뀐 것을 모르고 반쯤 고친 파일을 내보낼 일은 없다.

심층 검증은 Claude Design 런타임이 대신 호출해 주는 기능이라 파일 하나로
떼어내면 쓸 수 없다. 버튼을 누르면 그 이유를 적어 준다. 심층 검증까지 보여야
하면 Claude Design 링크를 쓴다.


## 10. 진행 상황

```
완료
  공통 스키마, 저장 레이어, 스냅샷, 누수 차단 (테스트 11건 통과)
  29CM 베스트 랭킹 수집기 및 일별 자동 수집
  터미널 리포트와 대시보드 2종 (수집 현황, 케이스 분석)
  인구통계 쏠림 리프트, 후보별 특징 추출
  커머스 순위와 리뷰 신호 (벡터+어휘 하이브리드로 후보와 상품 연결)
  네이버 검색어 트렌드 / 쇼핑인사이트 수집기 (키 발급 및 실호출 확인 완료)
  상의 카테고리 코드 확인 (여성 50000167 / 남성 50000169)
  케이스 번들 생성 도구와 파일럿 케이스 1건 (cases/case_pilot_rugby)
  sqlite-vec 벡터 검색과 동의어 클러스터링 (테스트 28건 통과)
```

```
대기
  역추적 케이스 선정 기준 합의 후 케이스 선정 (real / noise)
  실데이터로 클러스터링 임계값 조정
  영문 상품명 대응 확대 (현재는 1차 범위 어휘만 손으로 대응)
  무신사 수집 허가 확보 시 무신사 수집 모듈 추가
```

## 월간 트렌드 검증 PoC

[설치와 실행 안내](docs/MONTHLY_POC.md), [세 아이템 실행 결과와 화면](docs/MONTHLY_POC_RESULTS.md)
