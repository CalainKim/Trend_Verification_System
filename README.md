# 트렌드 시그널 검증 시스템 - 데이터 수집 파이프라인

2026-2학기 자기주도프로젝트 (아주대 소프트웨어, 산업체 연계: 무신사)
담당 범위: 시그널 후보 수집, 정제, 정규화, 특징 추출

확정/보류/기각 판정은 팀원 담당이며 이 저장소의 범위가 아니다.
이 저장소는 검증 단계에 넘길 입력값을 만드는 데까지만 책임진다.


## 1. 아키텍처

두 개의 트랙으로 구성한다.

```
데이터 소스

  트랙 A · 역추적 (메인)  ─ 과거 구간 소급 조회가 되는 API만 쓴다
      네이버 데이터랩 검색어 트렌드   국내 관심도 (메인 지표)
      네이버 쇼핑인사이트             성별·연령 분해
      Google Trends                  해외 선행 여부
      뉴스 아카이브                   캠페인 시점 (반증 근거)

  트랙 B · 실시간 축적 (보조)  ─ 크롤링, 소급 수집 불가
      29CM 베스트 랭킹   순위 · 리뷰 수 · 좋아요 수 · 품절 여부
      매일 쌓지 않으면 그날치는 영구 손실
  │
  ▼
collectors/   소스별 수집 모듈
  │   형식·주기·노이즈 특성이 달라 모듈은 나누고
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
  ├──▶ analytics.py  ─ 결측일 · 순위 변화 · 반증 신호
  │      └──▶ report.py (터미널) · build_dashboard.py (대시보드)
  │
  ▼
정제 · 정규화                              (미구현)
  │   동의어·유사 표현을 하나의 후보로 묶는다
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
··│···························· 이 저장소의 범위는 여기까지
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
  네이버 쇼핑인사이트 API             카테고리/키워드 클릭 추이, 성별·연령 분해
  Google Trends                       해외 선행 여부 검증
  뉴스 아카이브                       캠페인·미디어 노출 시점 확인 (반증 근거)

트랙 B
  29CM 베스트 랭킹 API                순위, 리뷰 수, 좋아요 수, 품절 여부
```

무신사 랭킹은 robots.txt가 화이트리스트 방식이라 자체 수집기를 전면 차단한다.
수집 허가가 나오기 전까지는 29CM를 대체 소스로 쓴다. docs/robots-compliance.md 참고.

29CM는 무신사 계열 서비스다(로그인 SSO와 주문 서비스 일부를 공유한다).
따라서 무신사와 29CM를 서로 독립적인 두 채널로 세면 안 된다. 교차검증에서는
같은 커머스 채널로 묶고, 독립 채널은 검색/쇼핑인사이트 쪽에서 확보한다.


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

  정제        결측/중복/이상치 처리, 동의어 및 유사 표현을 임베딩 기반 유사도로
              묶어 하나의 후보로 통합한다. (미구현)

  특징 추출   후보별로 채널별 변화 추이, 채널 간 시차, 캠페인과의 시간적 연관성,
              성별·연령 분포, 클릭 대비 전환 지표를 요약한다. (미구현)

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
유니섹스 상품은 여성·남성 랭킹에 동시에 오르므로 이렇게 하지 않으면 한 쪽이
유실된다. 리뷰 수와 좋아요 수는 상품 자체의 속성이라 상품 단위로 한 번만 저장한다.

누수 차단은 두 번 한다. 수집 단계에서 거르는 것과 별개로,
export.write_case_bundle()이 파일을 쓰기 직전 assert_no_leakage()로
observed_at < T_cut을 재검증한다. 한 건이라도 위반하면 번들 생성 전체가 중단된다.

케이스 번들의 meta.json에는 label과 T_peak을 쓰지 않는다. 정답은 수집 담당자만
trend_case 테이블에 보관하고, 검증팀에 전달되는 폴더는 블라인드 상태로 둔다.
정답을 보고 끼워맞추는 것을 막기 위함이다.


## 5. 저장 스키마

```
signal_raw            원시 수집 데이터. 모든 채널이 공유한다.
signal_candidate      동의어 클러스터링 결과. 흩어진 표현을 하나의 후보로 묶은 것.
candidate_keyword_map 후보와 원시 레코드의 연결.
candidate_summary     후보별 채널 요약. 검증 단계로 넘어가는 입력값.
trend_case            역추적 케이스의 정답. 산출물로 내보내지 않는다.
```

정의는 src/trend_pipeline/schema.sql에 있다.


## 6. 디렉터리 구조

```
  src/trend_pipeline/
    models.py            RawRecord. 모든 소스가 공유하는 단일 레코드 표현
    schema.sql           SQLite 스키마
    storage.py           저장 레이어
    snapshots.py         일별 CSV 스냅샷 입출력
    export.py            케이스 번들 생성, 누수 차단
    collectors/
      base.py            수집기 공통 인터페이스, 요청 간격 제어
      cm29_rank.py       29CM 베스트 랭킹 수집기
    analytics.py         수집 데이터 요약 집계 (리포트와 대시보드가 공유)
  scripts/
    collect_daily.py     트랙 B 일별 수집 진입점
    load_snapshots.py    스냅샷으로부터 DB 재구성
    report.py            터미널 리포트
    build_dashboard.py   docs/index.html 생성
  data/snapshots/        수집 원본 CSV (커밋 대상)
  cases/                 역추적 케이스 산출물 (검증팀 전달용)
  docs/                  GitHub Pages 대시보드와 근거 문서
  tests/                 저장 및 누수 차단 계약 테스트
```


## 7. 기술 스택

```
  Python 3.12
  requests          HTTP 수집
  pandas            데이터 처리
  beautifulsoup4    HTML 파싱
  SQLite            저장 (표준 라이브러리 sqlite3)
  pytest            테스트
  GitHub Actions    일 2회 자동 수집 (KST 09:00, 21:00)
```

임베딩 기반 유사도 계산 라이브러리는 정제 단계 착수 시점에 추가한다.


## 8. 실행

```
  python3.12 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  cp .env.example .env          네이버 API 키 입력

  python scripts/collect_daily.py             상의 카테고리 일간 랭킹 100위 수집
  python scripts/collect_daily.py --status    누적 현황 출력
  python scripts/load_snapshots.py            스냅샷으로부터 DB 재구성
  python scripts/report.py                    터미널 리포트
  python scripts/build_dashboard.py           대시보드 생성
  python -m pytest tests -q                   테스트
```


## 9. 진행 상황

```
완료
  공통 스키마, 저장 레이어, 스냅샷, 누수 차단 (테스트 11건 통과)
  29CM 베스트 랭킹 수집기 및 일별 자동 수집
  터미널 리포트와 정적 대시보드 (수집 결측일, 순위 변화, 반증 신호)
```

```
대기
  네이버 데이터랩 / 쇼핑인사이트 수집기 (API 키 발급 필요)
  Google Trends 수집기
  역추적 케이스 선정 (real / noise)
  동의어 클러스터링, 특징 추출
  무신사 수집 허가 확보 시 무신사 수집 모듈 추가
```
