# 사람 평가 양식 사용 안내

이 폴더는 `evidence-priority-v1`의 **빈 작성 양식**이다. 작성된 평가 결과나 모델 실행 예제가 아니다. null과 빈 문자열은 미작성 상태이며 0점·오류 없음·합의 완료를 뜻하지 않는다.

**사람이 직접 작성할 때는 [복사해서 쓰는 평가표](WORKSHEETS.md)부터 연다.** 근거 기준표, 출력 평가표, 합의표를 노션이나 문서에 복사해 사용할 수 있다. 아래 JSON은 같은 기록을 구조적으로 보관하기 위한 보조 양식이다. 문서 평가표를 JSON으로 자동 변환하는 기능은 아직 없다.

## 작성 순서

1. [작성용 근거 기준표](WORKSHEETS.md#1-모델-출력-전-근거-기준표)를 응도와 도은이 각각 복사한다. 모델 출력 전에 사실·중요 반대 근거·미확인 정보를 작성하고, 근거 묶음의 해시와 원문 위치를 남긴다. 구조화 저장은 [근거 기준표 JSON](reference-review.template.json)을 사용한다.
2. 두 원본을 유지하고 [합의 기록](consensus.template.json)에 기준표 합의와 미해결 항목을 적는다. 합의한 기준표 자체는 `reference-review.template.json` 형식의 새 파일로 저장한다.
3. 모델 실행 시 [실행 명세](run-manifest.template.json)를 작성한다. 이번 문서 작업에서는 실행하지 않았다. 모델·방법 대응표는 [가림 대응표](blind-map.template.json)에 별도로 보관한다.
4. 두 사람이 모델·방법을 가린 출력에 대해 [출력 평가표](output-review.template.json)를 각각 작성한다. 원문을 읽을 수 있는 기술 실패는 진단만 가능하며 유효 출력으로 바꾸지 않는다.
5. 최초 평가의 일치도·불일치를 보존하고 별도의 합의 기록을 작성한다. [요약표](review-summary.template.md)에 건수와 분모를 옮긴다. 미완료 평가는 미완료로 둔다.

평가용 화면에는 blind ID, 후보·근거 묶음, 출력 원문, 검증 가능한 근거를 제공한다. 모델명·방법명·호출 순서·가림 대응표는 제공하지 않는다. 원문 문체만으로 추측될 수 있는 한계는 있다. 단순히 JSON에 blind ID를 넣는 것만으로 블라인드 평가를 수행했다고 표시하지 않는다.

## 공통 작성 규칙

- `template`은 작성 사본에서 false로 바꾸고 실제 ID·시간대 포함 시각·파일 해시를 기록한다. 빈 템플릿은 집계 대상에서 제외한다.
- 배열에 있는 빈 항목은 필드 설명용이다. 실제 항목 수만큼 복사하고 쓰지 않는 빈 항목은 제거한다. 없는 근거를 채워 넣지 않는다.
- 같은 사실이 summary와 claims에 반복되면 사실 주장은 한 번만 세고 출력 위치를 모두 기록한다. 인용이 없는 사실 주장도 평가에서 빠뜨리지 않는다.
- 근거 ID는 동결 묶음의 실제 ID만 쓴다. 원문 위치는 줄 번호·표 행·문단·URL의 발췌 위치 등 다른 사람이 찾을 수 있게 적는다.
- 평가는 `SPEC.md`, 수식과 분모는 `EVALUATION.md`를 따른다. 작성 형식이 있다고 해서 자동 검증기나 집계 프로그램이 구현된 것은 아니다.
- 이름 대신 reviewer ID를 써도 되지만 두 평가자를 구분할 수 있어야 한다. 독립 평가 파일을 합의 결과로 덮어쓰지 않는다.
- 추후 저장 기본 위치는 버전이 분리된 `private/evidence-priority-v1/`로 정한다. 이 폴더의 공개 템플릿에는 API 키·개인 정보·가림 대응의 실제 값을 넣지 않는다.

## 선택지

| 필드 | 허용할 값 |
|---|---|
| `phase` | `reference_independent`, `reference_consensus`, `output_independent`, `output_consensus` |
| `method` | `direct`, `structured` — 비공개 실행 기록에서만 사용 |
| `verdict` | `PRIORITIZE`, `DEPRIORITIZE`, `HOLD` |
| 사실 주장 `assessment` | `supported`, `unsupported`, `contradicted`, `unverifiable`, `not_reviewed` |
| 반대 근거 `assessment` | `addressed`, `missed`, `misrepresented`, `not_reviewed` |
| 판정 적절성 `assessment` | 모든 판정에 대해 `appropriate`, `inappropriate`, `unresolved`, `not_assessable` 중 하나 |
| HOLD 전용 적절성 `assessment` | HOLD일 때 위 네 값 중 하나. HOLD가 아닌 경우에만 null |
| `execution_status` | `valid`, `invalid`, `incomplete`, `failed`, `not_run` |
| `has_major_error` | true, false, null. null은 오류 여부 미확정 |
| `agreement_status` | `agreed`, `disagreed`, `unresolved` |

`model-output.template.json`은 모델이 반환할 구조를 보여주는 빈 양식이며 실제 유효 응답이 아니다. 템플릿 자체를 모델 결과로 저장하거나 통과 사례로 세지 않는다.
