# 패션 트렌드 탐지 · 1차 MVP

**여러 상품에서 함께 나타나는 상승을 스타일 유형으로 묶고, 후보와 선정 이유를 보여준다.**

2026-2학기 산업체 연계 프로젝트. 29CM 상의 랭킹을 중심으로 후보를 찾고, Google Trends 검색 자료와 주별 변화를 함께 제공한다.

[한눈에 보기](docs/spec-v1/README.md) · [MVP 스펙](docs/spec-v1/SPEC.md) · [실행 안내](docs/spec-v1/LOCAL_RUNBOOK.md) · [Claude 프롬프트](docs/spec-v1/CLAUDE_PROMPT.md)

![MVP 전체 흐름](docs/diagrams/mvp-overview.svg)

[편집 가능한 draw.io 원본](docs/diagrams/mvp-overview.drawio)

## 해결할 문제

상품별 순위와 검색 신호가 흩어져 있어 어떤 스타일이 여러 상품·브랜드에 걸쳐 오르는지 파악하기 어렵다. 한 주의 상승만으로는 원래 큰 카테고리와 새롭게 커지는 유형도 비슷해 보인다.

이 MVP는 자료를 모으고, 유형을 묶고, 상승·브랜드 분산을 계산하고, 여러 주의 변화와 함께 후보를 보여준다. 문제 정의의 출처와 한계는 [근거 기록](docs/spec-v1/SOURCES.md)에 구분했다.

## 현재 구현

| 구성 | 코드 | 결과 |
| --- | --- | --- |
| 수집·원본 저장 | src/trend_pipeline/collectors, snapshots.py, storage.py | CSV + SQLite |
| 상품 속성 연결 | scripts/extract_attributes.py, data/attributes.yml | 상품과 검색 키워드 연결 |
| 유형·화면 데이터 | scripts/export_frontend.py | 상품, 검색, 비교 날짜 |
| 후보·다주 추적 | scripts/track_types.py | 후보 상태, 방향, 관측 요약 |
| 기존 화면 | design/Trend Monitor v8.dc.html, scripts/patch_design.py, bundle_design.py | Trend Monitor HTML |

![현재 구현의 연결](docs/diagrams/implementation.svg)

[draw.io 원본](docs/diagrams/implementation.drawio) · [상세 아키텍처](docs/spec-v1/ARCHITECTURE.md)

기본 입력은 29CM 남성·여성 상의 각각 TOP100이다. 의류 분류를 구매자의 성별·연령으로 해석하지 않는다. 신규 또는 10위 이상 상승한 상품 수, 브랜드 수와 집중도로 유형 후보를 선정하고 주별 랭킹 내 유형 상품 수의 변화를 함께 표시한다.

관측 요약 점수는 유행 확률이나 미래 판매 예측값이 아니다. [탐지 규칙과 산식](docs/spec-v1/SPEC.md)에 계산 기준을 명시했다.

## 실행

Python 3.12 기준. API 키 없이 저장된 실제 스냅샷으로 후보를 재현할 수 있다.

```bash
python -m pip install -r requirements-mvp.txt
python scripts/load_snapshots.py
python scripts/track_types.py --json build/type-tracks.json
python scripts/export_frontend.py --json --no-lead
```

화면을 실행 HTML로 조립하는 OS별 명령과 생성 결과는 [로컬 실행 안내](docs/spec-v1/LOCAL_RUNBOOK.md)를 따른다. 사진 다운로드를 생략하는 빌드도 제공한다.

## 확인한 해결 범위

이번 작업에서 저장 스냅샷 148,677행을 재적재하고, 최신 남녀 상의 200개 중 194개의 속성 연결과 9개 유형의 5주 비교를 재현했다. 나머지 6개는 속성 미매칭이다. 매칭률은 분류 정확도가 아니다.

후보 생성·선정 근거·변화 추적은 재현 가능하다. 광고 원인, 계절성 분리, 20대 남성 구매 반응, 실제 판매 연결과 현업 시간 절감은 확인된 성과에 넣지 않는다.

## 데이터와 개발 안내

- 원본: `data/snapshots/`. DB는 원본에서 재구성하는 파생물이다.
- `observed_at`은 지표의 관측 시점, `collected_at`은 수집 시점이다.
- 실수집은 `scripts/collect_daily.py`, `scripts/collect_gtrends.py` 등 기존 진입점을 사용하며 출처와 인증 설정이 필요하다.
- NAVER 수집 코드·저장 자료는 보유하고 있으나 기본 탐지 화면의 검색 추이는 Google Trends에서 읽는다.
- GitHub 수집 워크플로는 수동 실행이다. 29CM 실수집은 실행 환경의 접근 가능 여부에 영향을 받는다.
- NAVER 상대 지수는 서로 다른 요청 사이의 절대량으로 비교하지 않는다.
- 기본 탐지 데모에는 임베딩 모델이 필요하지 않다. 별도 벡터 검색은 `requirements.txt`의 추가 의존성을 사용한다.
- 테스트: `python -m pip install -r requirements-test.txt` 후 `python -m pytest -q`. Windows의 짧은 임시 경로 설정은 실행 안내를 참고한다.
- 비밀키·개인 자료·DB·빌드 결과는 커밋하지 않는다.

## 문서

[MVP 문서 모음](docs/spec-v1/README.md) · [draw.io 도면](docs/diagrams/README.md) · [수집 정책 기록](docs/robots-compliance.md)

기존 별도 기록: [월별 분석](docs/MONTHLY_POC.md), [검증 파트 인계](docs/verification-handoff.md), [주간 보고](docs/weekly/2026-11-03-10주차.md). 해당 문서의 모델 판정·채점·리뷰 흐름은 이번 탐지 MVP의 필수 기능이 아니다.
