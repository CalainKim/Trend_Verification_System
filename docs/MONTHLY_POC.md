# 3개 스타일의 4월 판단과 월별 결과

헨리넥·럭비티·링거티의 **3~4월 자료에 대한 모델의 선정 근거 → 이후 변화 → 판단 비교**를 같은 형식으로 보여준다. 이전 반팔티·맨투맨·카라티 실행은 수정하지 않는다.

화면 위의 세 아이템 카드에서 4월 쇼핑 증감률을 비교하고, 카드를 선택하면 해당 아이템의 수치와 지지·반대 이유를 확인할 수 있다. 후속 자료를 아직 조회하지 않았다면 빈 그래프 대신 `5~10월 미조회`를 표시하고, 선정 근거에는 모델의 판단 요약과 지지·반대 이유를 먼저 보여준다. 3~4월 수치는 상세보기에서 확인한다. 두 요청의 지수를 섞지 않는다. 외부 기록·원문·실행 조건은 상세보기에서 확인한다. 아이템 전환은 네트워크나 스크립트 없이 작동하며, 인쇄 시에는 세 사례를 모두 출력한다.

## 실행

프로젝트 루트의 `.env`에 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `ANTHROPIC_API_KEY`가 필요하다. 키는 출력물에 저장하지 않는다. 현재 키의 제공처는 네이버 클라우드 API HUB다. 개발자센터 키를 사용할 때만 `--provider developers`와 새 `--run-dir`를 지정한다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-poc.txt
.\.venv\Scripts\python.exe scripts/monthly_poc.py collect
.\.venv\Scripts\python.exe scripts/monthly_poc.py review
.\.venv\Scripts\python.exe scripts/monthly_poc.py evaluate
.\.venv\Scripts\python.exe scripts/monthly_poc.py report
.\.venv\Scripts\python.exe scripts/serve_poc.py --run-dir private/monthly-poc/2025-styles-v1 --port 8767
```

브라우저 주소는 `http://127.0.0.1:8767/`다. 저장된 HTML은 외부 스크립트 없이 열 수 있다. `run`은 위 수집·검토·후속 조회·보고서 단계를 순서대로 실행한다. `report`, `status`, `audit`는 API를 호출하지 않는다. 보고서 새로고침과 다운로드도 추가 호출이 없다.

## 자료와 정책

- 초기 입력: 2025-03-01~04-30, 후속 그래프: 2025-03-01~10-31. 두 요청은 독립 보존하며 지수를 이어 붙이지 않는다.
- 집계: 네이버가 제공하는 `timeUnit=month`. 일별 결측을 임의로 0으로 채워 월평균을 만들지 않는다. 월간 응답에 없는 월도 0이 아닌 결측이다.
- 쇼핑: 남성 티셔츠 `50000169`, `gender=m`, `ages=[20]`, 기기 전체. 검색: `gender=m`, `ages=[3,4]`로 19~29세 보조 자료. 동의어를 자동 합산하지 않는다.
- 코드 기준: 같은 초기 요청의 4월 지수가 3월의 1.2배 이상이면 관찰 후보. 3월 0 또는 월 누락은 보류. 20%는 비교용 초기 기준이며 실제 유행의 정의가 아니다.
- AI: `claude-opus-5-5`, `effort=low`, 출력 상한 4,096토큰, 아이템당 1회. 지지·반대·미확인 항목 각각 최대 2개. 내부 사고 과정 대신 출처가 연결된 결과를 받는다.
- 모델 입력에는 자기 아이템의 3~4월 관측·계산·조회 조건만 포함한다. 출처 선정 문서, 사후 기사, 5~10월 자료, 정답 분류, 이전 사람 판단은 제외한다. 현재 소급 조회이므로 2025년 당시의 모델·자료 가용성을 재현한 실험은 아니다.

참고: [네이버 월간 쇼핑 API](https://api.ncloud-docs.com/docs/naver-api-hub-shopping-insight-keywords), [검색 API 연령 구간](https://developers.naver.com/docs/serviceapi/datalab/search/search.md).

## 외부 기록과 비교

`data/cases/monthly-2025.json`에 검색어 범위와 공식 플랫폼 원문 링크·게시일·고객군을 고정한다. 당시 기록을 참고해 고른 설명용 사례이며 정답률 평가용 무작위 표본은 아니다. 자료가 원하는 세 유형으로 나뉘지 않으면 실제 결과를 그대로 표시한다.

출처가 수요 관측의 시작일과 종료일을 명시한 경우에만 해당 기간을 음영으로 표시한다. 상품 출시일·기사 게시일·촬영일 추정은 수요 관측 기간으로 사용하지 않는다. 게시일만 확인되면 타임라인의 점으로 표시한다. 편집 상품 소개와 브랜드 전체 실적을 해당 스타일의 구매 확산으로 바꾸지 않는다.

`assessment.json`은 저장된 AI 응답과 후속 요청 해시에 연결한 별도 사후 검토다. 문장별 사실 확인, 추가 설명의 도움, 과장·미확인을 기록한다. 이 파일을 작성한 도구의 검토를 사람의 최종 판단으로 표시하지 않는다. 모델 원문은 변경하지 않는다. AI와 숫자 판단이 같으면 새로운 후보 선별 성능을 입증했다고 쓰지 않는다.

## 저장·실패·재시작

기본 폴더는 Git에서 제외된 `private/monthly-poc/2025-styles-v1/`다.

- `requests/`, `initial-requests.json`, `followup-requests.json`: 실제 응답·조건·조회 시각·해시.
- `sources.json`, `plan.json`, `frozen.json`: 사례 선정 및 초기 근거와 API 입력 고정 기록.
- `cases/01..03/`: 초기 번들, 실제 API 요청·응답, 검토 기록, 개별 HTML·JSON·CSV.
- `index.html`, `suite.json`, `comparison.csv`: 세 사례 비교 및 다운로드.
- `completion.json`: 후속 자료·초기 응답 무결성 검사에 사용하는 해시.

실패·중단된 호출은 일반 `review`나 `run`으로 재실행하지 않는다. 일부 검토가 완료되지 않으면 후속 조회를 막고 실패 상태로 보고서를 만들 수 있다. 사용자가 추가 유료 실행을 승인한 경우에만 다음 명령으로 실패한 사례 하나를 다시 실행한다.

```powershell
.\.venv\Scripts\python.exe scripts/monthly_poc.py retry-review --case 1
```

이전 실패 원문과 부분 응답은 해당 사례의 `attempts/`에 남는다. 정상·진행 중·전체 완료된 호출은 이 명령으로도 재실행하지 않는다. 스트림 중 미리보기 파일이 잠기는 경우 로컬 파일 쓰기만 짧게 재시도하고, 미리보기 실패가 API 스트림 자체를 끊지 않도록 처리한다. API 자동 재시도는 없다.

```powershell
.\.venv\Scripts\python.exe scripts/monthly_poc.py audit
.\.venv\Scripts\python.exe -m pytest tests/test_trend_poc_monthly.py tests/test_trend_poc_monthly_report.py tests/test_trend_poc_naver.py tests/test_trend_poc_review.py -q
```

검증에는 20% 경계, 월 누락·기준값 0, 고객군 조건, 요청 단위 해시, 미래 자료 격리, 완료 전 후속 조회 차단, 인용 ID·정상 종료, 중복 과금 방지, 출처 날짜·집계 범위, 완료 후 원문 변경 차단을 포함한다.

## 현재 확인한 결과

세 아이템의 API 검토가 저장됐으며 헨리넥은 실패 기록을 보존한 뒤 명시적 재실행으로 완료했다. 헨리넥·럭비티는 관찰 지지 어려움, 링거티는 관찰 후보다. 5~10월 후속 비교와 설명의 효과 평가는 아직 완료하지 않았다.

이번 판단은 4월까지의 자료를 본 뒤 나온 것이다. 4월 상승을 미리 예측한 결과가 아니다. 입력에는 코드 판단과 해석상의 한계도 들어가므로, 현재 결과만으로 모델의 독립적인 기여를 입증하지 않는다.
