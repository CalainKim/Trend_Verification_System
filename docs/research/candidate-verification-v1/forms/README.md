# 사람 검토와 평가 양식

이 폴더는 `candidate-verification-v1`의 **빈 양식**이다. 실험 결과나 완료된 평가가 아니다. null·빈칸은 미작성이고 0점·오류 없음·합의 완료가 아니다.

먼저 [복사해서 쓰는 평가표](WORKSHEETS.md)를 연다. 아래 JSON은 같은 기록을 구조적으로 저장하기 위한 양식이며 문서를 자동 변환하는 도구는 아니다. 실행기의 `run.json`을 사람 평가 양식으로 대체하지 않는다.

| 작성 시점 | 양식 |
|---|---|
| 후보·실험 계획을 출력 전에 고정 | [study-plan.template.json](study-plan.template.json) |
| 인터뷰 해석을 원문과 대조 | [interview-review.template.json](interview-review.template.json) |
| 각 평가자가 사실·중요 반대 근거·미확인 정보를 표시 | [reference-review.template.json](reference-review.template.json) |
| 조건·모델 대응표를 별도 보관 | [blind-map.template.json](blind-map.template.json) |
| 두 평가자가 공통 최종 출력을 독립 판독 | [output-review.template.json](output-review.template.json) |
| 최초 평가를 보존하고 합의 기록 | [consensus.template.json](consensus.template.json) |
| 독립 평가 후 조사·반증 경로 진단 | [investigation-review.template.json](investigation-review.template.json) |
| 사람이 최종 결정·수정 이유 기록 | [human-decision.template.json](human-decision.template.json) |
| 미래 반응을 별도 추적 | [followup.template.json](followup.template.json) |
| 분자·분모와 미측정 상태 집계 | [review-summary.template.md](review-summary.template.md) |

## 작성 규칙

- 작성 사본에서는 `template=false`로 바꾸고 실제 ID·시간대 포함 시각·해시를 기록한다. 공개 템플릿에 개인 발화나 실제 가림 대응표를 넣지 않는다.
- 빈 배열 항목은 필드 설명용이다. 실제 항목만 남기며 없는 근거를 만들지 않는다.
- 동일 사실이 요약과 근거 설명에 반복되면 한 번만 세고 모든 출력 위치를 기록한다. 인용 없는 사실 주장도 평가한다.
- 평가자가 서로 다르게 나눈 사실 주장은 최초 값을 수정하지 않고 의미가 같은 원자 주장인지 연결해 일치도 분모를 정한다. 연결할 수 없는 항목과 이유를 별도 보고한다.
- 가림 자료는 두 조건의 공통 최종 필드와 실제 근거로 구성한다. 모델·조건·실행 순서·`criterion_reviews`는 제공하지 않는다. 문체로 추측할 수 있는 한계는 기록한다.
- 실제 제공 근거로 주장 지원을 판독하고, 전체 동결 자료집의 기준표로 중요한 반대 근거 누락을 판독한다. 조사 누락과 해석 누락을 구분한다.
- 사람 최종 결정, 사람 평가, 모델 제안, 미래 후속 관측은 서로 다른 기록이다. 어느 것도 미래 유행의 자동 정답으로 바꾸지 않는다.
- 기록 기본 위치는 비공개 `private/candidate-verification-study/`다. 초기 독립 기록을 합의본으로 덮어쓰지 않는다.

## 선택지

| 필드 | 허용 의미 |
|---|---|
| `condition` | `with_interview`, `without_interview` — 가림 대응표·실행 계획에서만 노출 |
| 모델 제안·사람 최종 판정 | `CONFIRM`, `HOLD`, `REJECT` |
| 주장 판독 | `supported`, `unsupported`, `contradicted`, `unverifiable`, `not_reviewed` |
| 논리 판독 | `coherent`, `invalid`, `unresolved`, `not_assessable` |
| 논리 오류 | `unsupported_leap`, `self_contradiction`, `circular_reasoning`, `ignored_counterevidence`, `scope_shift` |
| 반대 근거 | `addressed`, `missed`, `misrepresented`, `not_reviewed` |
| 판정·HOLD 적절성 | `appropriate`, `inappropriate`, `unresolved`, `not_assessable`; HOLD가 아니면 HOLD 항목은 해당 없음 |
| 실행 상태 | `complete`, `api_error`, `schema_error`, `not_run` — 실행 전 `configuration_error`는 미실행 사유로 기록 |
| 인터뷰 해석 검토 | `accept`, `revise`, `exclude`, `unresolved`; 검토자의 해석 확인이지 가설 입증이 아님 |
| 최초 의견과 합의 | `agreed`, `disagreed`, `unresolved` |

분모·미평가·기술 실패 처리는 [평가 명세](../EVALUATION.md)를 따른다. 평가 양식이 있다는 사실만으로 자동 집계기나 사람 평가가 완료되었다고 표시하지 않는다.
