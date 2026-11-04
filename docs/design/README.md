# 트렌드 모니터 화면 작업 (진행 중)

목표: 증권 터미널처럼 뜨는 속성을 보여주고, 누르면 근거와 관련 상품이 나오고,
판정이 버텼는지까지 채점해 보여주는 B2B 웹 화면. 갱신은 하루 1~2회면 충분하다.

    DESIGN_BRIEF.md       트렌드 모니터 브리프 (화면 3장, 데이터 규칙 6개)
    mock-data.json        그 숫자 원본. 2026-11-02 DB 기준 실제 값
    RETROSPECT_BRIEF.md   회고 화면 브리프 (휴대폰 1순위, 데이터 규칙 6개)
    retrospect-mock.json  그 숫자 원본. 시점 3개로 줄인 사본

    ../../scripts/build_design_mock.py   mock-data.json 을 다시 만든다
    ../../scripts/build_retrospect.py    retrospect-mock.json 을 다시 만든다

회고 화면은 과거 한 시점으로 돌아가 그때 오른 검색어를 보여 주고, 결과를
가린 채 사용자가 먼저 찍게 한 뒤 펼친다. 트렌드 모니터와 자료가 다르고
목적도 다르므로 브리프를 따로 둔다.

## 지금 상태 (2026-11-02)

1. 브리프와 데이터로 Claude Design 시안 "Trend Monitor v8" (8페이지)을 만들었다.
   아직 검토하지 않았다. 시안을 Export 해서 이 폴더에 넣으면 검토부터 이어간다
2. 검토 기준은 DESIGN_BRIEF.md 5절의 데이터 규칙
3. 다음 단계: 시안을 기준으로 로컬 웹 앱을 만든다 (DB 를 읽어 새로고침).
   판정은 아직 연결 전이다. Claude 판정을 지속성 벤치마크에 붙여 채점하는 것이 그다음이다

## 다른 컴퓨터에서 이어갈 때

- `.env` 는 저장소에 없다. `.env.example` 을 복사해 네이버 키와 `ANTHROPIC_API_KEY` 를 넣는다.
  `ANTHROPIC_WORKSPACE_ID` 는 비워도 된다
- Claude 판정 코드(`src/trend_poc`)는 `anthropic` 패키지가 필요하다: `pip install -r requirements-poc.txt`
- DB 가 없으면 `python scripts/load_snapshots.py` 로 복원한다
- `mock-data.json` 을 다시 만들면 숫자가 바뀌어 브리프의 표와 어긋난다. 브리프도 같이 고친다
