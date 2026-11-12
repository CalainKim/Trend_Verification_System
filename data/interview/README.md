# 후보 검증용 인터뷰 가설 입력

[candidate-hypotheses-v1.json](candidate-hypotheses-v1.json)은 사용자 제공 패션 토론 전사문 전체에서 AI가 추출한 **정확히 10개**의 검토 가설이다. 데이터 상태는 `AI_selected_unreviewed`이며 모든 항목은 `reviewed=false`다.

이 파일은 현재 `trend_verification_v1.inputs.validate_criteria` 계약을 따른다. 각 항목에는 `id`, `hypothesis`, `question`, `expected_evidence`, `applicability`, `counterexamples`, `source_ref`, `reviewed`가 있다. 원문에 없는 비율·점수·가격 임계값이나 개인 일화는 넣지 않았다. `counterexamples`는 기계적인 단정을 막기 위한 적용 예외·주의 상황이다.

## 실행 의미

사용자가 요청한 실제 모델의 지시 수행·가설 적용 동작 점검에 입력할 수 있다. **실제 API를 썼다는 사실이 사람 검토 완료나 가설 입증을 뜻하지 않는다.** 모델 적용 상태는 `applied_as_hypothesis`, `not_applicable`, `insufficient_evidence`를 사용하고 미검토 항목을 `applied`로 취급하지 않는다. 모든 가설을 충족해야 확정하거나 자료가 하나라도 없으면 보류하는 규칙이 아니다.

이 파일 자체는 실제 스타일 사례나 시장 관측 데이터가 아니다. 합성 후보로 실행하면 입력 가설의 출처가 실제 전사문이더라도 결과는 합성 사례의 동작 점검이다. 당시 실제 원자료로 실행해도 이번 진단을 독립적인 본 평가로 표시하지 않는다.

## 출처와 공개 범위

`source_ref=interview-map:iv1-Hn`은 비공개 `private/interview-source-map.json`의 익명 키다. 비공개 매핑에는 원본의 SHA-256, 문자 시작·끝 위치, 짧은 정확 발췌와 발췌 해시가 있다. 공개 JSON에는 원문 발췌·개인 식별 정보·첨부 파일 경로가 없다.

원래 합성 데모용 `data/examples/candidate-verification/criteria.json`을 덮어쓰지 않는다. 현재 10개 가설의 사용·변경은 별도로 기록한다. 사람의 원문 해석 검토가 완료되면 이 파일을 몰래 수정하는 대신 버전·검토 기록·새 해시를 고정한다.

각 가설의 의미와 중복을 피한 구분은 [가설 설명](../../docs/research/candidate-verification-v1/INTERVIEW_HYPOTHESES.md)에 있다.
