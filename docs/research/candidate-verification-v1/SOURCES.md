# 출처와 자료의 사용 경계

2026-11-12 · `candidate-verification-v1`

## 문제 정의의 근거

| 출처 | 확인한 내용 | 사용 경계 |
|---|---|---|
| 사용자가 제공한 원래 작업 대화의 최초 요청 | 후보를 확정하거나 기각하는 검증 시스템이라는 과제 | 비공개 프로젝트 요구 기록. 기업 담당자의 직접 발언으로 인용하지 않음 |
| [GitHub 최초 인수인계](https://github.com/CalainKim/Trend_Verification_System/blob/39705408a432eba670fe7002bbe1e3e3391e21df/docs/verification-handoff.md#L81) | 절차의 투명성·반증 가능성 | 전체 기업 요구사항의 확정본으로 확대하지 않음 |
| [GitHub 인수인계의 평가·태스크](https://github.com/CalainKim/Trend_Verification_System/blob/8886fa181f314a001b090cdbb24752dd89aedc0b/docs/verification-handoff.md#L468) | 근거와 반증, 사람이 최종 판단, 별도 반증 단계 | 과거 지속성 정답 실험과 현재 근거 검증을 구분 |
| 사용자 제공 실제 전사문 | 목표 집단·관심과 구매·홍보·계절·착용 수용성에 대한 논의 | ASR 오류·발화자 불확실성이 있어 사람 검토 전 연구 가설로 요약 |

전사문 원문은 비공개 작업 자료이며 공개 저장소에 복사하지 않는다. 직접 인용, 발화자 신원, 개인 일화, 임의 비율은 논문에 옮기지 않는다. 원문 구간의 접근 가능한 비공개 위치와 해석 검토 이력은 [가설 검토 양식](forms/interview-review.template.json)으로 남긴다. [취지 대조](ALIGNMENT.md)와 [가설 표](INTERVIEW_HYPOTHESES.md)를 함께 본다.

## 관련 연구와 공식 명세

| 출처 | 방법 설계에서 참고한 내용 | 주장하지 않는 내용 |
|---|---|---|
| [Gao et al., 2023, ALCE](https://aclanthology.org/2023.emnlp-main.398/) | 답변 정확성과 인용 품질을 구분하는 평가 | 우리 후보 판정의 타당성이나 ALCE 점수 재현 |
| [Yao et al., 2023, ReAct](https://arxiv.org/abs/2210.03629) | 정보 접근 행동과 언어 모델 작업 수행의 연결 | 우리 방법의 효과가 이미 입증됐다는 주장, 내부 사고 과정 검증 |
| [Turpin et al., 2023](https://arxiv.org/abs/2305.04388) | 설명이 내부 판단 요인의 충실한 기록은 아닐 수 있다는 한계 | 현재 모델 오류의 구체적 원인이 그 연구와 같다는 단정 |
| [네이버 검색 API](https://developers.naver.com/docs/serviceapi/datalab/search/search.md) | 연령 코드와 상대 검색 지수의 정의 | 검색이 실제 구매량이라는 주장 |
| [네이버 쇼핑인사이트 API](https://developers.naver.com/docs/serviceapi/datalab/shopping/shopping.md) | 검색 클릭 추이의 정의 | 주문·매출·시장 전체 수요의 직접 관측 |

위 논문은 학회 공식 페이지 또는 저자 제출 arXiv의 제목·저자·연도·초록을 확인했다. API는 공식 명세를 확인했다. 문헌의 전체 실험을 재현한 것은 아니다. 선행 연구는 방법의 배경이며 본 연구 결과를 대신하지 않는다.

## 자료별 용도

| 자료 | 용도 | 새 본 평가에 포함 여부 |
|---|---|---|
| [합성 후보·자료집·가설](../../../data/examples/candidate-verification/) | 단계 연결, 조건 격리, 인용·실패·시점 검사의 예제 | 제외. 시장의 실제 관측이 아님 |
| [기존 맨투맨 출력](../forecast-v2-outputs.json)과 [점검 기록](../FORECAST_V2_RESULTS.md) | 이전 상품 과제의 환경·지시 수행 확인 | 제외. 새 스타일 검증 과제의 성능 결과가 아님 |
| 헨리넥·럭비티·링거티의 과거 자료 | 자료 구성과 방법 설명 | 제외. 이미 결과를 알고 선정한 설명 사례 |
| [이전 우선순위 설계](../priority-v1/PAPER_DRAFT.md) | 변경 이력 | 과제·평가 결과를 자동 이전하지 않음 |
| 새 후보·당시 원자료 | 인터뷰 제공 유무의 본 비교 | 선정·수집·동결 전. 현재 측정값 없음 |
| 미래 반응 | 후속 관측 기록 | 현재 판정의 정답·성공률 계산에 합산하지 않음 |

과거 스타일 자료의 시점·공개 여부에 관한 자세한 구분은 [당시 출처 기록](../priority-v1/SOURCES.md)을 보존한다. 실제 본 평가 자료로 새로 사용하려면 현재 기준으로 원문과 시점을 다시 확인하고 가설·출력·평가 라벨이 섞이지 않았는지 검사한다.
