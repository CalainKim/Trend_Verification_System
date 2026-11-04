# 트렌드 모니터 화면 작업 (진행 중)

목표: 증권 터미널처럼 뜨는 속성을 보여주고, 누르면 근거와 관련 상품이 나오고,
판정이 버텼는지까지 채점해 보여주는 B2B 웹 화면. 갱신은 하루 1~2회면 충분하다.

    DESIGN_BRIEF.md       트렌드 모니터 브리프 (화면 3장, 데이터 규칙 6개)
    mock-data.json        그 숫자 원본. 2026-11-02 DB 기준 실제 값
    RETROSPECT_BRIEF.md   회고 화면 브리프 (휴대폰 1순위, 데이터 규칙 6개)
    retrospect-mock.json  그 숫자 원본. 시점 3개로 줄인 사본
    TIMELINE_BRIEF.md     날짜 구간 화면 브리프 (두 축의 깊이가 다르다)
    timeline-mock.json    그 숫자 원본. 속성은 한국만, 상품은 40개로 줄인 사본

    ../../scripts/build_design_mock.py   mock-data.json 을 다시 만든다
    ../../scripts/build_retrospect.py    retrospect-mock.json 을 다시 만든다
    ../../scripts/build_timeline.py      timeline-mock.json 을 다시 만든다

회고 화면은 과거 한 시점으로 돌아가 그때 오른 검색어를 보여 주고, 결과를
가린 채 사용자가 먼저 찍게 한 뒤 펼친다. 트렌드 모니터와 자료가 다르고
목적도 다르므로 브리프를 따로 둔다.

## 지금 상태 (2026-11-04)

1. v9 시안을 적용했다. `design/Trend Monitor v9.dc.html` 이 원본이고
   `./scripts/build_viewer.sh` 가 파일 하나로 묶는다. 결과 이름에 시안 번호가
   들어가므로 v8 로 만든 것도 같이 남는다. 옛 시안으로 만들려면
   `SRC="design/Trend Monitor v8.dc.html" ./scripts/build_viewer.sh`
2. v9 가 새로 들고 온 것: 날짜 구간 선택(달력), 회고 화면, 무신사 로고,
   명령 창(Ctrl+K), React 컴포넌트 일곱
3. 남은 것
   - 달력이 속성 축(2021-12 부터)을 모른다. TIMELINE_BRIEF.md 를 보라
   - 휴대폰 폭에서 3단 레이아웃이 접히지 않는다. PWA 는 따로 만든다

## 다른 컴퓨터에서 이어갈 때

- `.env` 는 저장소에 없다. `.env.example` 을 복사해 네이버 키와 `ANTHROPIC_API_KEY` 를 넣는다.
  `ANTHROPIC_WORKSPACE_ID` 는 비워도 된다
- Claude 판정 코드(`src/trend_poc`)는 `anthropic` 패키지가 필요하다: `pip install -r requirements-poc.txt`
- DB 가 없으면 `python scripts/load_snapshots.py` 로 복원한다
- `mock-data.json` 을 다시 만들면 숫자가 바뀌어 브리프의 표와 어긋난다. 브리프도 같이 고친다
