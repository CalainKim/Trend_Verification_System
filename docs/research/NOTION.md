# 20대 남성 상의 트렌드 리즈닝 연구

2026-11-11 · 교수님 검토용 초안 · evidence-priority-v1

**현재 근거로 계속 관찰할 스타일 후보와 그 이유를 판단한다.** 연구의 중심은 검증 방법과 **근거 → 해석 → 판정의 논리적 타당성**이다. 네이버·SNS는 후보를 찾는 트리거이고, 리즈닝은 과거 기록과 추가 자료에서 지지·반대 근거를 검토한다.

| 확정한 범위 | 현재 구현 상태 | 아직 검증하지 않은 부분 |
|---|---|---|
| 한국 20대 남성 상의 스타일의 관찰 우선순위 | Claude·A40 연결과 기존 실행·저장 경로 확인 | 새 우선순위 과제의 모델 동작·사람 평가·비교 효과 |

이번 산출물은 **논문 초안·판정 명세·평가 양식·구조도**다. 새 과제의 실행기 연동과 본 실험은 후속 단계이며, 이번에는 모델 호출이나 GPU 가동을 하지 않았다. 비용·속도·사용 토큰은 연구 질문과 평가 지표에서 제외한다.

## 먼저 볼 자료

- [교수님 검토용 논문 초안](https://github.com/CalainKim/Trend_Verification_System/blob/codex/reasoning-paper-pilot/docs/research/priority-v1/PAPER_DRAFT.md)
- [판정 기준과 기본·구조적 검토 프롬프트](https://github.com/CalainKim/Trend_Verification_System/blob/codex/reasoning-paper-pilot/docs/research/priority-v1/SPEC.md)
- [평가 지표와 두 사람의 검토 절차](https://github.com/CalainKim/Trend_Verification_System/blob/codex/reasoning-paper-pilot/docs/research/priority-v1/EVALUATION.md)
- [바로 복사해 쓰는 사람 평가 양식](https://github.com/CalainKim/Trend_Verification_System/tree/codex/reasoning-paper-pilot/docs/research/priority-v1/forms)
- [편집 가능한 draw.io 2페이지와 미리보기](https://github.com/CalainKim/Trend_Verification_System/tree/codex/reasoning-paper-pilot/docs/research/priority-v1/diagrams)
- [초기 초안·GitHub 문서와 취지 대조](https://github.com/CalainKim/Trend_Verification_System/blob/codex/reasoning-paper-pilot/docs/research/priority-v1/ALIGNMENT.md)

## 시스템은 무엇을 하나

초기 인수인계부터 근거 추적성과 반증 가능성을 우선했다는 점에서 이번 방향은 일치한다. 이후 추가된 순위 예측 실험과 별도 반증 호출까지 완료한 것은 아니며, 이번 범위는 **근거를 해석하고 판단하는 방법의 1차 검증 설계**다.

후보 등록 → 근거 수집·정제 → 시점·대상·중복 확인 → 근거 묶음 고정 → 리즈닝 → 관찰 우선순위 카드 → 사람 검토

![후보 등록부터 근거 검토와 사람 판단까지](https://raw.githubusercontent.com/CalainKim/Trend_Verification_System/refs/heads/codex/reasoning-paper-pilot/docs/research/priority-v1/diagrams/priority-architecture.png)

| 판정 | 뜻 |
|---|---|
| PRIORITIZE · 우선 관찰 | 중요한 반대 근거를 고려해도 계속 관찰할 구체적인 이유가 남음 |
| DEPRIORITIZE · 우선순위 낮춤 | 대상 불일치·반복 홍보·관측된 약화 등 구체적 근거가 있음 |
| HOLD · 보류 | 필요한 자료가 부족하거나 중요한 근거가 충돌함 |

미래 실제값이 없다는 이유만으로 보류하지 않는다. 광고가 있다는 사실만으로 우선순위를 낮추지 않는다. 카드에는 근거 ID, 부족한 정보, 무엇이 확인되면 판단을 바꿀지를 함께 적는다.

## 리즈닝을 어떻게 검증하나

**같은 후보·같은 근거·같은 출력 형식**으로 기본 판정과 구조적 검토를 비교한다. 구조적 검토는 대상 적합성 → 출처 독립성 → 지지 근거 → 반대 설명 → 불확실성의 순서로 판단한다. 두 방법을 Claude와 Qwen에 각각 적용하는 설계다.

응도와 도은이 모델 답변을 보기 전에 사실·중요 반대 근거·미확인 정보의 기준표를 만든다. 이후 모델명과 방법명을 가린 출력을 각자 평가하고, 최초 평가와 합의 결과를 따로 보존한다.

| 지표 | 확인할 내용 |
|---|---|
| 주장 근거 충실도 | 사실 주장을 원자료가 실제로 뒷받침하는가 |
| 판단 논리의 타당성 | 근거에서 해석과 판정으로 이어지는 연결에 비약·모순·순환논증이 없는가 |
| 반대 근거 반영률 | 중요한 반대 관측을 빠뜨리거나 왜곡하지 않았는가 |
| 중대한 오류 | 수치·단위·시점·대상 혼동이나 근거 없는 단정이 있는가 |
| 판정·보류 적절성 | 판단 이유와 부족한 정보가 구체적이고 근거에 맞는가 |
| 전체 처리 결과 | 우선 관찰·낮춤·보류·기술 실패를 모두 집계 |
| 평가자 일치도 | 합의 전 항목별 일치 정도와 판정 일치표 |

분모가 없으면 해당 없음, 아직 읽지 않았으면 미평가로 기록한다. 기술 실패를 정상 보류나 오류 없음으로 처리하지 않는다. 보류를 늘리거나 주장 수를 줄여 좋아진 지표도 다른 결과와 함께 해석한다.

![같은 근거 비교와 두 평가자의 독립 검증](https://raw.githubusercontent.com/CalainKim/Trend_Verification_System/refs/heads/codex/reasoning-paper-pilot/docs/research/priority-v1/diagrams/priority-evaluation.png)

## 지금까지 확인한 것

2026-11-08 Qwen 재실행은 **최소 과제 수행 3/8건, 형식·근거 ID까지 함께 통과 2/8건**이었다. 5건은 미래 실제값 부재를 판단 중단이나 반대 근거로 사용했다. AI 보조 동작 점검 기록이며 예측 정확도나 사람 평가 결과가 아니다.

- 맨투맨 8상품: 기존 환경과 지시 수행의 점검 기록으로 보존한다.
- 헨리넥·럭비티·링거티: 방법을 설명하는 과거 사례로 사용한다. 독립 성능 평가 표본은 아니다.
- 새 본 평가: 사례·근거·설정·사람 기준표를 별도로 고정한 뒤 진행한다. 아직 결과를 측정하지 않았다.

## 논문의 주장과 후속 관측

논문은 ‘구조적 근거 검토가 오류와 논리적 비약을 줄이고 반대 근거 처리를 개선하는가’를 묻는다. Claude와 Qwen은 같은 검토 방법이 다른 모델에서도 일관되게 동작하는지 확인하는 보조 축이다. 시계열은 근거의 한 종류이며, 모델 내부 사고 과정의 정확성이나 실제 판매 증가를 입증한다고 쓰지 않는다.

미래 반응은 우선 관찰뿐 아니라 보류·우선순위를 낮춘 후보도 별도로 추적한다. **4주 안에 뜨지 않으면 실패라는 기준은 없다.** 반응이 관측되지 않았다면 해당 관측 시점까지 미관측이라고 남긴다.

목표 집단은 20~29세 남성이지만 네이버 검색의 연령 코드 3+4는 19~29세다. 대상 범위를 정확히 표시하고, 연령 미확인 기사나 상품 자료를 20대 남성의 반응으로 단정하지 않는다. 검색·클릭을 구매량으로 표현하지 않는다.

## 구현체와 이전 기록

- [전체 연구 문서와 구현 경계](https://github.com/CalainKim/Trend_Verification_System/blob/codex/reasoning-paper-pilot/docs/research/README.md)
- [자료와 참고문헌](https://github.com/CalainKim/Trend_Verification_System/blob/codex/reasoning-paper-pilot/docs/research/priority-v1/SOURCES.md)
- [11월 8일 Qwen 동작 확인과 실제 출력](https://github.com/CalainKim/Trend_Verification_System/blob/codex/reasoning-paper-pilot/docs/research/FORECAST_V2_RESULTS.md)
- [이전 노션 본문 보관](https://github.com/CalainKim/Trend_Verification_System/blob/codex/reasoning-paper-pilot/docs/research/archive/NOTION-forecast-v2.md)
- [초안 PR #18](https://github.com/CalainKim/Trend_Verification_System/pull/18)

과거 실행 기록을 유지한다. 새 명세를 기존 pilot-v1·forecast-v2 실행 옵션에 덮어쓰지 않으며, 운영 관리 항목은 연구 평가와 분리한다.
