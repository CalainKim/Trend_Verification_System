# 인터뷰 가설과 AI 조사를 결합한 트렌드 후보 검증

2026-11-12 · 현재 과제 `candidate-verification-v1`

**시계열에서 초기 후보를 찾고, 인터뷰에서 정리한 검토 가설과 당시 자료를 이용해 AI가 조사·반증한다. 확정·보류·기각을 제안한 뒤 사람이 최종 결정한다.** 연구는 출력의 근거 충실성과 판단 논리의 타당성을 검증한다. 미래 유행 여부는 별도 후속 관측이다.

| 구분 | 현재 범위 |
|---|---|
| 대상 | 한국 20대 남성 상의 스타일 키워드 |
| 방법 | 초기 신호 → 가설·맥락 → 제한된 자료 조사 → 별도 반증 → AI 제안 → 사람 최종 판단 |
| 비교 | 같은 절차에서 인터뷰 가설 제공/미제공, Claude/Qwen의 보조 모델 축 |
| 구현 | 조사 실행 경로, 합성 예제, 실제 모델 연결과 누적 실행 제한, 단계·근거·판정을 읽는 로컬 화면 |
| 미완료 | 실제 인터뷰 해석 검토, 새 후보·자료집 수집과 동결, 실제 모델 본 비교, 사람 독립 평가 |

## 먼저 볼 문서

| 문서 | 확인할 내용 |
|---|---|
| [교수님 검토용 초안](candidate-verification-v1/PAPER_DRAFT.md) | 연구 문제·방법·평가 설계·한계 |
| [초기 취지 대조](candidate-verification-v1/ALIGNMENT.md) | 원래 검증 시스템과 현재 범위의 관계 |
| [인터뷰 가설](candidate-verification-v1/INTERVIEW_HYPOTHESES.md) | 실제 전사문에서 정리한 검토 전 가설과 확인 절차 |
| [판정·조사 명세](candidate-verification-v1/SPEC.md) | CONFIRM/HOLD/REJECT, 조사·반증·격리 계약 |
| [평가 명세](candidate-verification-v1/EVALUATION.md) | 동일 자료집 비교, 출력 근거·논리 판독, 분모와 실패 처리 |
| [바로 쓰는 사람 평가표](candidate-verification-v1/forms/WORKSHEETS.md) | 기준표·독립 판독·합의·사람 최종 판단 |
| [로컬 구현 안내](candidate-verification-v1/IMPLEMENTATION.md) | 합성 데모와 실제 연구 준비의 구분 |
| [실제 모델 동작 점검](candidate-verification-v1/LIVE_CHECK.md) | 보관된 링거티 개발 사례의 실제 출력·실패와 해석 한계 |
| [출처 기록](candidate-verification-v1/SOURCES.md) | 초기 요청·문헌·전사문·기존 자료의 사용 경계 |
| [편집 가능한 구조도](candidate-verification-v1/diagrams/candidate-verification-v1.drawio) | 시스템과 평가 구성 |
| [노션용 방법론 요약](NOTION.md) | 숫자·설정·결과를 분리한 설명 |

![시스템 구성](candidate-verification-v1/diagrams/candidate-architecture.png)

## 실제로 무엇을 확인하나

새 후보 6건 × 모델 2개 × 인터뷰 조건 2개로 최종 출력 24건을 비교하는 계획이다. 이는 호출 수가 아니다. 두 조건은 같은 초기 근거·동결 자료집·검색기·조사 한도·별도 반증 절차·모델 내 설정을 사용한다. 가설 없는 조건은 모든 단계에서 가설과 앞 조건의 답을 격리한다.

새 실제 후보 선정과 본 비교는 아직 하지 않았다. 별도로 보관된 링거티 실제 관측에 AI가 선정한 미검토 가설을 적용하는 [실제 모델 동작 점검](candidate-verification-v1/LIVE_CHECK.md)을 실행했다. 미제공 조건에서 완료된 출력이 있지만 인터뷰 제공 조건의 전체 절차는 출력 계약 오류로 완료하지 못했다. 이는 개발 사례의 운영 확인이며 본 평가 표본이 아니다. 합성 데모의 모델 이름은 비교 칸이며 실제 모델이 생성한 답이 아니다. 저장 기록을 보여 주는 로컬 화면은 기존 사이트에 배포된 기능이나 실시간 API가 아니다.

출력 전 두 사람이 사실·중요 반대 근거·미확인 정보 기준표를 만든다. 가린 공통 출력을 독립 평가하고 최초 불일치와 합의를 따로 남긴다. 미래의 실제 반응이나 사람의 최종 선택을 이 평가의 자동 정답으로 삼지 않는다.

## 이전 기록은 별도 보존

- [이전 관찰 우선순위 초안](priority-v1/PAPER_DRAFT.md): `evidence-priority-v1`의 설계 이력. 현재 실행·비교 설계로 사용하지 않는다.
- [이전 연구 첫 화면](archive/README-priority-v1.md), [이전 노션 본문](archive/NOTION-priority-v1.md): 변경 전 원문. 상대 링크는 당시 `docs/research/` 기준이다.
- [상품 순위 동작 점검](FORECAST_V2_RESULTS.md), [실제 출력](forecast-v2-outputs.json), [과거 실행 안내](RUNBOOK.md): `pilot-v1`·`forecast-v2`의 별도 기록.
- [과거 우선순위 출처 기록](priority-v1/SOURCES.md): 실제·합성·후향적 자료의 구분.
- [운영 제약](OPERATIONS.md): 기존 운영 기록을 그대로 유지한다.

과거 출력·평가·봉인 해시는 변경하지 않는다. 새 과제 결과와 합산하거나 판정 이름만 바꾸어 이전하지 않는다.
