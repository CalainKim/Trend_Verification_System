# 1차 MVP 로컬 실행 안내

저장소에 포함된 실제 스냅샷으로 **트렌드 후보를 찾고, 관련 상품과 주별 변화를 확인하는 흐름**을 재현한다. 새 수집, API 키, LLM 호출, 모델 다운로드 없이 실행한다. 이 문서의 숫자는 기능 재현 결과이며 현업의 업무 시간 단축이나 탐지 정확도를 측정한 결과는 아니다.

## 1. 설치

저장소 루트에서 실행한다. 권장 환경은 Python 3.12이며, 이번 로컬 점검은 Windows Python 3.13에서 수행했다. PR CI는 Ubuntu / Python 3.12로 같은 테스트와 스냅샷 재현을 실행하도록 구성했다. CI 통과 여부는 PR의 실행 결과에서 확인한다.

PowerShell:

```powershell
python -m venv .venv
$mvpPython = (Resolve-Path .venv/Scripts/python.exe).Path
& $mvpPython -m pip install -r requirements-test.txt
$env:PYTHONUTF8 = '1'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
```

실행만 필요하면 `requirements-mvp.txt`를 설치한다. `requirements-test.txt`는 여기에 pytest를 추가한다. 기존 `requirements.txt`는 별도 벡터 색인·임베딩 작업과 실시간 수집을 위한 전체 의존성이다. 이번 스냅샷 데모에는 설치하지 않아도 된다.

macOS/Linux에서는 `python3 -m venv .venv` 후 아래 명령의 `& $mvpPython`을 `.venv/bin/python`으로 바꾼다.

## 2. 자료 복원과 후보 변화 확인

```powershell
& $mvpPython scripts/load_snapshots.py
& $mvpPython scripts/export_frontend.py --json --no-lead
& $mvpPython scripts/extract_attributes.py --out build/attribute_map.csv --top 8
& $mvpPython scripts/track_types.py --json build/type-tracks.json
```

| 명령 | 하는 일 | 결과 |
| --- | --- | --- |
| `load_snapshots.py` | 버전 관리된 CSV를 SQLite에 적재 | `data/signals.sqlite` |
| `export_frontend.py` | 최신 주 상품·속성·검색 추이·유형 변화를 화면 형식으로 변환 | `build/frontend_data.js`, `.json` |
| `extract_attributes.py` | 상품명에서 사전의 속성·표기 변형을 찾음 | `build/attribute_map.csv` |
| `track_types.py` | 주별 후보 상태와 TOP100 내 상품 수의 변화를 계산 | `build/type-tracks.json` |

`--no-lead`는 해외 선행 일수 계산만 생략한다. 해당 결과에 선행 값이 없다는 것은 계산을 생략했다는 뜻이다. 해외 신호가 없다고 결론 내리지 않는다. 이 옵션 없이 실행해도 새 API 호출은 없지만 저장 시계열의 선행 계산 시간이 추가된다.

`load_snapshots.py`는 이미 적재한 행을 다시 넣지 않는다. 새 체크아웃에서는 아래와 같은 전체 적재 수가 나오고, 재실행에서는 신규 0행이 정상이다. 기존 DB를 지우는 명령은 필요 없다.

## 3. 기존 Trend Monitor 화면 만들기

2절의 `export_frontend.py`를 먼저 실행한다. 화면 패치 스크립트는 기본 위치인 `build/frontend_data.js`를 읽는다.

```powershell
& $mvpPython scripts/patch_design.py 'design/Trend Monitor v8.dc.html' -o build/mvp-patched.html
& $mvpPython scripts/bundle_design.py build/mvp-patched.html --assets design/runtime -o build/trend-monitor-mvp.html --skip-images
Start-Process -FilePath (Resolve-Path build/trend-monitor-mvp.html).Path
```

결과는 `build/trend-monitor-mvp.html` 한 파일이다. CSS·JS·폰트와 수집 수치를 포함한다. `--skip-images`는 상품 사진을 다운로드하지 않으므로 사진 표시는 인터넷 연결이 필요하다. 후보·상품 목록과 숫자를 확인하는 데 모델 호출은 필요 없다.

기존 화면의 선택적 AI 분석과 판정 기록 기능은 이번 MVP 시연의 필수 경로가 아니다. API 키를 입력하거나 해당 기능을 실행할 필요가 없다. 이 문서의 빌드는 키를 파일에 넣는 `--embed-key` 옵션을 사용하지 않는다.

`docs/index.html`은 기존 수집 현황 대시보드다. 위 명령으로 만든 Trend Monitor와 역할이 다르므로 문서나 PR에서 두 화면을 같은 구현으로 표기하지 않는다.

## 4. 이번에 재현한 현재 구현

확인 기준: `main`의 `3b8d574`를 바탕으로 한 2026-11-03 스냅샷. 비교 날짜는 저장소의 수집분이 추가되면 바뀐다.

| 항목 | 실행 결과 | 해석 범위 |
| --- | --- | --- |
| 스냅샷 복원 | 148,677행 | 저장된 관측 자료의 행 수 |
| 화면 비교 날짜 | 10/20 → 10/27 → 11/03 | 기준·감지·확인 시점 |
| 비교 상품 | 시점별 200개 | 29CM 남성·여성 상의 TOP100 각각 100개 |
| 화면에 연결된 상품 | 194 / 200개 | 6개는 속성 사전에 매칭되지 않아 화면 목록에서 빠짐 |
| 화면 속성 / 검색 추이 | 52개 / 40개 | 속성별 관측 자료가 같은 수준으로 채워진 것은 아님 |
| 전체 상품명 속성 매칭 | 2,439 / 2,455개, 99.3% | 사전에 1개 이상 매칭된 비율이며 분류 정확도가 아님 |
| 유형 추적 | 9개 유형, 5주 | 09/29~11/03의 스냅샷으로 주간 변화 계산 |
| 연속 후보이면서 확대 | 맨투맨·후드·탑 | 현재 규칙에 따른 관측 요약, 미래 유행 확정 아님 |

이 상품 화면에는 구매자의 나이가 없다. NAVER의 연령·성별 교차 조회 기능과 구분해야 하며, 29CM 상품 목록 전체를 ‘20대 남성 반응’으로 해석하지 않는다.

현재 유형 규칙은 `scripts/track_types.py`에 있다. 직전 주 대비 10계단 이상 상승하거나 새로 진입한 상품을 모으고, 상승 상품 3개 이상·브랜드 3곳 이상·최대 브랜드 점유율 50% 이하이면 후보로 표시한다. 유형의 방향은 TOP100 내 상품 수의 앞·뒤 구간 평균을 비교한다. 이 값들은 인터뷰에서 승인된 기준이나 검증된 정확도가 아니라 현재 구현의 초기 규칙이다.

화면 생성 과정에는 기존 코드의 `CASES`, `SCORE`, `LEDGER`도 포함된다. 이 부가 출력의 수치를 1차 MVP의 문제 해결률이나 탐지 정확도로 보고하지 않는다.

## 5. 실행 품질 확인

PowerShell에서 짧은 임시 경로를 쓰면 긴 테스트 이름과 응답 파일명이 합쳐지는 Windows 경로 길이 문제를 피할 수 있다. 아래 경로는 pytest가 관리하는 전용 임시 폴더로만 사용한다.

```powershell
$mvpTestTemp = Join-Path $env:TEMP ('trend-mvp-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
& $mvpPython -m pytest tests -q -p no:cacheprovider --basetemp $mvpTestTemp
```

최소 의존성만 설치한 새 가상환경에서, 스냅샷 내보내기까지 마친 뒤 전체 테스트 **360개 통과**를 확인했다. 화면 데이터 생성 전에는 이미지 중복 검사 1개가 건너뛰어져 359개 통과였으며, 생성 후에는 해당 항목도 통과했다. 실제 자료로 만든 3.7MB 화면 파일의 인라인 JavaScript 6개도 문법 검사를 통과했다.

이번 변경으로 빈 벡터 색인 검색은 모델을 다운로드하지 않고 빈 결과를 반환하며, 수집일이 없는 주별 추적은 자료 부족을 안내한다. 사진 다운로드를 생략하는 옵션도 기존 화면 빌드에 추가했다. 기능 검사 결과와 현업 효과 측정을 혼동하지 않는다.

## 6. 이 데모에서 확인할 순서

1. 유형별로 무엇이 확대·유지·축소하는지 확인한다.
2. 선택한 유형에 어떤 속성과 실제 상품이 연결되는지 확인한다.
3. 상품의 순위 변화, 브랜드 분포와 자료 날짜를 함께 확인한다.
4. 사전에 잡히지 않는 상품과 부족한 자료를 확인한다.

재고 발주 자동화, 향후 매출 예측, 모델 비교 점수, 추가 리뷰 절차는 이 시연의 완료 조건에 포함하지 않는다.
