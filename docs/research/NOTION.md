# 패션 트렌드 후보를 조사하고 검증하는 방법

**시계열에서 초기 후보를 찾고, 인터뷰에서 정리한 검토 가설과 당시 자료를 이용해 AI가 조사·반증한다. AI는 확정·보류·기각을 제안하고 사람이 최종 결정한다.**

연구의 중심은 출력이 근거에 충실한지, 그 근거에서 판정으로 이어지는 논리가 타당한지 확인하는 것이다. 인터뷰는 조사할 질문을 만들고 실제 자료를 해석하는 데 사용한다. 인터뷰에 나온 생각 자체를 사실이나 정답으로 취급하지 않는다.

| 확정한 범위 | 현재 구현 | 아직 확인하지 않은 부분 |
|---|---|---|
| 한국 20대 남성의 상의 스타일 후보 검증 | 조사·반증·판정 기록 화면을 연결하고 보관된 실제 자료로 모델 연결과 출력 계약의 문제를 확인 | 인터뷰 가설 포함 절차의 정상 완료, 가설의 도움과 출력 근거·판단 논리의 타당성 |

## 무엇을 해결하려는가

관심이 늘어난 스타일이 발견되어도 누구의 반응인지, 반복 홍보인지, 계절적 필요로 설명되는지, 실제 착용·채택과 연결되는지 바로 알기 어렵다. 후보를 채택하거나 기각하려면 지지 자료와 반대 설명을 함께 조사해야 한다.

한국 20대 남성의 상의 스타일을 대상으로 이 검증 절차를 구성한다. 시계열은 초기 변화를 발견하고 이후의 흐름과 확산을 해석하는 근거다. 인터뷰 검토 가설은 조사 방향을 잡는 질문이며, 당시의 원자료가 최종 설명의 근거가 된다.

## 어떻게 동작하는가

후보 등록 → 당시 근거 준비 → 인터뷰 가설과 맥락 검토 → AI 주도 조사 → 별도 반증 → 확정·보류·기각 제안 → 사람의 최종 판단

![후보 탐지에서 AI 조사와 사람 최종 판단까지](https://raw.githubusercontent.com/CalainKim/Trend_Verification_System/refs/heads/codex/reasoning-paper-pilot/docs/research/candidate-verification-v1/diagrams/candidate-architecture.png)

AI는 미리 고정한 자료집에서 부족한 정보와 반대 설명을 찾는다. 조사와 분리된 반증 단계가 지지 근거의 약점, 대상 혼동, 반복 출처, 다른 설명을 점검한다. 최종 카드에는 판정 이유, 지지·반대 근거, 미확인 정보와 판단을 바꿀 조건을 담는다.

| 제안 | 의미 |
|---|---|
| CONFIRM · 확정 제안 | 중요한 반대 설명을 검토해도 현재 후보 가설을 채택할 근거가 남음 |
| HOLD · 보류 제안 | 핵심 자료가 부족하거나 중요한 근거가 충돌함 |
| REJECT · 기각 제안 | 현재 후보 가설을 받아들이기 어렵다는 구체적인 반대 근거가 있음 |

확정은 미래 유행의 보장이 아니다. 미래값이 아직 없다는 이유만으로 보류하지 않고, 광고가 있다는 사실만으로 기각하지 않는다. 사람은 제안을 수용하거나 수정하고 그 이유를 따로 남긴다.

## 지금 확인하고 있는 것

전사문에서 AI가 선정한 질문 10개를 미검토 가설로 정리하고, 보관된 링거티 실제 자료에 조사·반증 절차를 연결해 실제 모델의 조건별 실행을 확인했다. 사람이 원문 해석을 승인했거나 가설을 입증한 상태는 아니다. 가설을 제공하지 않는 조건에는 가설과 다른 조건의 답이 전달되지 않는다.

자료의 대상 범위와 측정 의미를 구분해 설명하는 출력이 확인됐다. 가설의 적용 상태값이 검사 규칙과 맞지 않거나 필수 항목을 빠뜨린 출력도 있어, 프롬프트의 선택 규칙과 필수 출력을 더 명료하게 설명하는 개발 진단을 분리했다. 실패와 원문을 보존하며 이를 곧바로 모델의 판단 능력 실패로 단정하지 않는다. 가설의 효과와 논문 본 평가의 성과는 별도 검토가 필요하다.

추가 진단에서는 가설별 행을 받았지만 인용 항목 누락과 적용 상태 오류가 남아 유효한 최종 제안으로 이어지지 못했다. 실제 모델 연결과 실패 기록은 확인했으며, 인터뷰 가설을 포함한 전체 절차는 출력 구조를 더 보완해야 한다. 구조를 강제하거나 가설별 출력을 분리해 검사하는 방안은 다음 구현 과제다.

이 자료는 과거 관측을 나중에 확보해 현재 시점에 다시 읽은 개발 사례다. 당시 유행을 미리 찾아냈거나 현재 수요를 확인했다는 결과로 사용하지 않는다.

## 방법을 어떻게 검증하는가

같은 초기 근거와 같은 자료집에서 **인터뷰 가설을 제공한 조건과 제공하지 않은 조건**을 비교한다. 조사·반증 절차는 동일하게 두며 서로 다른 모델에서도 같은 비교를 수행한다. 질문과 획득한 근거가 달라질 수 있으므로 조사와 판단 전체의 차이를 살핀다.

평가자는 모델 출력 전에 자료집의 사실·중요 반대 근거·미확인 정보를 표시한다. 이후 모델명과 조건을 가린 공통 출력을 각자 검토하고, 최초 불일치와 나중의 합의를 별도로 보존한다. 가설 적용 기록과 조사 경로는 독립 판독 뒤 진단한다.

![같은 자료집에서 인터뷰 유무를 비교하고 출력의 근거와 논리를 판독](https://raw.githubusercontent.com/CalainKim/Trend_Verification_System/refs/heads/codex/reasoning-paper-pilot/docs/research/candidate-verification-v1/diagrams/candidate-evaluation.png)

| 평가 관점 | 확인하는 내용 |
|---|---|
| 근거 충실성 | 사실·수치·기간·대상이 실제 제공된 자료에 맞는가 |
| 논리적 타당성 | 전제에서 판정으로 이어지는 설명에 도약·모순·순환이 없는가 |
| 반대 근거 처리 | 중요한 반대 관측을 찾고 정확히 반영했는가 |
| 판정과 불확실성 | 보류·기각·확정의 이유와 추가 확인 조건이 구체적인가 |
| 절차의 투명성 | 조사·반증·수정 이유와 사람의 최종 판단을 다시 확인할 수 있는가 |

숨겨진 사고 과정의 정확성을 입증하는 연구는 아니다. 확인할 수 있는 출력과 근거의 관계를 검증한다. 미래 반응은 별도로 기록하고 현재 판정의 자동 정답으로 쓰지 않는다.

## 상세 문서와 구현

- [교수님 검토용 논문 초안](https://github.com/CalainKim/Trend_Verification_System/blob/codex/reasoning-paper-pilot/docs/research/candidate-verification-v1/PAPER_DRAFT.md)
- [원래 취지와 현재 범위의 대조](https://github.com/CalainKim/Trend_Verification_System/blob/codex/reasoning-paper-pilot/docs/research/candidate-verification-v1/ALIGNMENT.md)
- [인터뷰 가설과 해석 검토 절차](https://github.com/CalainKim/Trend_Verification_System/blob/codex/reasoning-paper-pilot/docs/research/candidate-verification-v1/INTERVIEW_HYPOTHESES.md)
- [판정·조사 계약과 평가 설계](https://github.com/CalainKim/Trend_Verification_System/tree/codex/reasoning-paper-pilot/docs/research/candidate-verification-v1)
- [사람이 작성하는 평가표](https://github.com/CalainKim/Trend_Verification_System/blob/codex/reasoning-paper-pilot/docs/research/candidate-verification-v1/forms/WORKSHEETS.md)
- [로컬 구현체·실행 안내·검증 범위](https://github.com/CalainKim/Trend_Verification_System/blob/codex/reasoning-paper-pilot/docs/research/candidate-verification-v1/IMPLEMENTATION.md)
- [실제 모델 동작 점검과 확인된 한계](https://github.com/CalainKim/Trend_Verification_System/blob/codex/reasoning-paper-pilot/docs/research/candidate-verification-v1/LIVE_CHECK.md)
- [편집 가능한 draw.io](https://github.com/CalainKim/Trend_Verification_System/blob/codex/reasoning-paper-pilot/docs/research/candidate-verification-v1/diagrams/candidate-verification-v1.drawio)

인터뷰 해석의 검토 상태, 실제 자료와 합성 자료의 구분, 세부 실험 조건과 구현 상태는 위 문서에서 관리한다.
