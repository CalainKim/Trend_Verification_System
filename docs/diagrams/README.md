# 1차 MVP draw.io 도식

트렌드 탐지의 문제, 방법론, 현재 구현을 세 장으로 설명한다. 원본은 모두 **편집 가능한 draw.io XML**이며, 카드·텍스트·연결선을 개별 수정할 수 있다. 카드 안의 텍스트는 카드와 함께 이동하고 주 흐름 연결선은 카드에 연결돼 있다.

| 그림 | 편집 원본 | 저장소용 SVG | 노션용 PNG |
| --- | --- | --- | --- |
| 문제 → 방법 → 산출물 | [mvp-overview.drawio](mvp-overview.drawio) | [SVG](mvp-overview.svg) | [PNG](mvp-overview.png) |
| 현재 구현 아키텍처 | [implementation.drawio](implementation.drawio) | [SVG](implementation.svg) | [PNG](implementation.png) |
| 후보 선정·주별 변화 규칙 | [detection-method.drawio](detection-method.drawio) | [SVG](detection-method.svg) | [PNG](detection-method.png) |

## 원본을 편집하는 방법

1. [draw.io](https://app.diagrams.net/) 또는 draw.io Desktop에서 `.drawio` 파일을 연다.
2. 카드의 텍스트와 연결선을 편집한다. 흰 배경, 맑은 고딕, 남색 제목·파랑 주 흐름·청록 보조 흐름을 유지한다.
3. 같은 이름의 SVG와 PNG를 다시 내보내 문서와 노션에 반영한다.

현재 파일은 **draw.io Desktop 32.6.1의 실제 내보내기 기능**으로 생성했다. SVG에는 편집 원본도 포함했다. PNG는 1.4배 해상도이며 모두 1MB 미만이다. 배포할 때는 SVG 또는 PNG와 `.drawio` 원본 링크를 함께 제공한다. 다른 운영체제에 맑은 고딕이 없으면 원본의 글꼴을 한글 지원 글꼴로 바꾸고 다시 내보낸다.

CLI가 설치돼 있다면 저장소 루트에서 다음과 같이 재생성할 수 있다. `drawio` 명령 대신 설치된 실행 파일 경로를 지정해도 된다.

```powershell
drawio --export --format svg --embed-diagram --theme light --border 0 --output docs/diagrams/mvp-overview.svg docs/diagrams/mvp-overview.drawio
drawio --export --format png --theme light --scale 1.4 --border 0 --output docs/diagrams/mvp-overview.png docs/diagrams/mvp-overview.drawio
```

나머지 두 그림도 같은 명령에서 파일 이름을 바꿔 내보낸다. [공식 내보내기 안내](https://www.drawio.com/docs/manual/export/export-diagram/)를 참고한다.

## 도식의 근거

| 그림의 내용 | 실제 구현 |
| --- | --- |
| 공통 관측 형식·저장·스냅샷 | [models.py](../../src/trend_pipeline/models.py), [storage.py](../../src/trend_pipeline/storage.py), [snapshots.py](../../src/trend_pipeline/snapshots.py) |
| 수집 출처 | [collectors](../../src/trend_pipeline/collectors/) |
| 속성 사전 및 상품명 유형 규칙 | [extract_attributes.py](../../scripts/extract_attributes.py), [export_frontend.py](../../scripts/export_frontend.py)의 `type_of` |
| 상승·브랜드·주별 방향·관측 점수 | [track_types.py](../../scripts/track_types.py), [persistence.py](../../src/trend_pipeline/persistence.py)의 `MIN_RISE` |
| 실제 관측을 화면 데이터로 연결 | [export_frontend.py](../../scripts/export_frontend.py), [patch_design.py](../../scripts/patch_design.py), [bundle_design.py](../../scripts/bundle_design.py) |

해석할 때 지켜야 할 범위:

- 원 전사문은 이 패키지에 없으므로 문제 상황은 **요구사항 정리용 작업 가설**이다. 다른 팀의 문제나 인터뷰 직접 인용으로 표시하지 않는다.
- 주 탐지 입력은 29CM의 남성·여성 상의 각 TOP100이다. 이 상품 카테고리는 실제 소비자의 나이·성별을 증명하지 않는다.
- 기본 모니터의 검색 시계열은 `export_frontend.py`가 `gtrends` 채널에서 가져온다. NAVER 수집·저장 구현을 기본 화면 연결 완료로 표시하지 않는다.
- 후보의 브랜드 점유율 분모는 **해당 유형의 상승 상품 수**다. 여러 브랜드라는 사실만으로 독립된 캠페인이나 자연 확산을 입증하지 않는다.
- 주별 방향의 15%는 **앞 절반과 뒤 절반의 유형별 상품 수 평균 변화**다. 주당 성장률이 아니다. 앞 구간 평균이 0이고 뒤 구간이 양수이면 코드가 확대·변화량 1.0으로 처리한다.
- 방향 계산은 주간 관측 4개 미만이면 현재 코드에서 `유지, 0.0`을 반환한다. 이는 충분한 자료로 안정성을 확인했다는 뜻이 아니다.
- 점수의 연속성은 현재까지의 연속 주 수가 아닌 **관측 기간 내 최대 연속 주 수**다. 분산은 마지막 주 상승 브랜드 수를 그 주의 해당 유형 상품 수로 나눈 값이다. 이 점수는 관측 요약이며 미래 유행 확률이 아니다.
- 구현 완료와 사용자 문제 해결 효과는 구분한다. 탐지 정확도와 업무 시간 절감률은 측정하지 않았으므로 성과 수치나 완성률로 적지 않는다.

## 내보내기 확인

2026-11-03에 세 `.drawio`를 공식 Desktop CLI로 열어 PNG·SVG로 내보냈다. 세 PNG에서 한글, 카드 간격, 텍스트 잘림·겹침, 연결선을 확인했다. SVG의 내장 XML도 파싱해 편집 가능한 셀이 남아 있고 대체 문자 오류가 없는지 확인했다.
