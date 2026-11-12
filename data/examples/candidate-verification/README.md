# 합성 후보 검증 동작 예시

`case.json`, `corpus.json`, `criteria.json`은 **실제 인터뷰·시장 관측·연구 사례가 아닌 합성 fixture**다. H1~H5는 검토 전 가설이며 `reviewed=false`, `source_ref=null`이다.

```text
python scripts/run_candidate_verification.py demo --output-dir private/candidate-verification
python scripts/run_candidate_verification.py inspect-config
python scripts/run_candidate_verification.py verify private/candidate-verification/<run_id>
```

기본 데모는 한 합성 후보를 Claude/Qwen이라는 비교 슬롯 × 인터뷰 포함/미포함에 배치한다. 실제 두 모델은 호출하지 않고 같은 scripted 클라이언트를 사용한다. 따라서 4개 출력의 차이나 일치를 모델 성능·인터뷰 효과로 해석할 수 없다. `distinct_original_sources`에 대한 데모 분기도 합성 이야기를 재생하기 위한 것으로 일반 판정 임계값이 아니다.

초기 자료에는 순위 상승과 독립 원출처 3개라는 집계가 있다. 이후 원본 대조에서 세 관측이 모두 한 원본의 재게시라는 정정 자료를 찾아, 제한 검색과 별도 반증을 거쳐 CONFIRM이 REJECT로 바뀌는 저장 경로를 보여준다. 기각하는 것은 제공된 묶음의 독립 관측 주장이지 미래 유행 가능성이 아니다. 미래 자료, 인터뷰 문서, 정답 문서, 다른 고객군, 재게시, 가용 시점 미확인 문서는 검색 결과에서 제외된다. 원자료와 제외 사유는 감사용으로 보존되지만 모델 요청에는 적격 관측만 들어간다.

각 실행은 새 `cv1-...` 폴더에 입력·요청·응답·검색·최종 기록을 배타적으로 생성한다. 기존 실행을 덮어쓰거나 예산 원장을 초기화하지 않는다. `verify`는 기록과 모든 동결 파일 해시를 다시 확인한다. 실제 평가 호출은 CLI와 실행기에서 잠겨 있다. 후속 승인은 기존 누적 예산 통합과 함께 별도로 구현해야 한다.
