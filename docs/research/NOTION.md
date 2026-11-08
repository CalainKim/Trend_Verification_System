# 트렌드 추론 · 환경과 1차 스펙 점검

실행일 2026-11-08 · 맨투맨 8상품 · Claude API / A40 Qwen3-8B

**이번 주 목적은 연구 환경 준비와 1차 구현·입출력 스펙 정리다.** 정식 연구 계획과 논문 결론은 이후 결정한다. 현재 수치로 모델 우열이나 시계열 결합 효과를 결론 내리지 않는다.

## 현재까지 확인한 것

| 항목 | 상태 |
|---|---|
| 환경 연결 | Claude API와 A40 Qwen3-8B 각각 8회 응답 수신 |
| 실행·저장 | 입력 구성, JSON 출력, 호출 기록, 해시 검증 경로 구현 |
| 기술 검증 | 총 154개 검사 통과. 16회 요청에서 기술 실패·재시도 없음 |
| 스펙 점검 | 예측 지시, HOLD 허용 조건, 평가 문턱의 의미를 보완할 항목 확인 |
| 비용·종료 | API+GPU 추정 약 $0.249, 저장·IOPS 별도. 실험 후 두 Pod 중지 확인 |
| 연구 설계 | 기존 연구 질문·A/B/C 비교·논문 구조는 미확정 후보 초안 |

정상 응답 수신은 예측 과제를 제대로 수행했다는 의미가 아니다. 실제 출력을 읽어 과제 해석까지 확인해야 한다.

## Qwen은 왜 7건을 보류했나

저장된 실제 시스템·사용자 프롬프트와 최종 출력 8건을 대조했다. **예측하라는 지시는 있었다. 다만 미래 예측과 미래값을 받은 뒤 확인하는 일을 충분히 구분하지 못했다.**

| 실제 프롬프트 | 빈틈 |
|---|---|
| “WATCH는 상승분 절반 이상 유지의 예측” | 예측이라는 역할은 명시돼 있음 |
| “확인 구간의 실제 순위는 입력에 없으며, 현재 입력만으로 예측한다.” | 핵심 안내 일부가 관측 JSON의 limitations 안에 있음 |
| “근거가 부족하면 HOLD를 사용” | 과거 자료의 부족과 미래 정답의 부재를 구분하지 않음 |
| 미래 관측을 근거로 추가하지 말 것 | 미래 관측을 지어내지 않는 일과 미래를 추정하는 일의 경계가 약함 |

**HOLD 7건 모두 미래 실측이 없다는 이유로 멈췄다.** 과거 흐름을 검토한 뒤 불확실성이 높다고 판단한 양상과 다르다.

실제 출력 예시:

> “확인 기간 데이터 부재로 판단 불가”
>
> “확인 기간 평균 순위 데이터 누락”

유일한 WATCH도 입력의 **판정 문턱 95.36위**를 “이후 7개 관측일 평균 95.36위”처럼 사용했다. 문턱은 미래 관측값이나 예측값이 아니다.

8건 모두 정상 종료됐고 출력은 543~2,370토큰으로 8,192 상한에 도달하지 않았다. 실제 응답과 저장된 판정도 모두 일치한다. 현재 기록에서는 메모리 부족·응답 잘림·후처리의 HOLD 변환으로 설명할 증거가 없다.

가장 강한 작업 가설은 **열린 보류 규칙 아래에서 Qwen이 예측을 사후 확인으로 해석했다는 것**이다. 프롬프트를 바꿔 비교하지 않았으므로 원인을 확정하거나 수정하면 해결된다고 보장하지 않는다.

## 1차 스펙에서 정리할 항목

| 구분 | 점검 내용 |
|---|---|
| 과제 | 판단 시점의 과거 흐름으로 이후 지속성을 예상한다는 역할 |
| 미래값 | 없는 것이 정상인 정답. 부재 자체만으로 HOLD하는 것과 관측값을 지어내는 것을 모두 구분 |
| HOLD | 과거 입력의 부족·충돌·불확실성 중 어떤 조건에 허용할지 |
| 판정 문턱 | 평가 기준과 실제 관측값·예측값의 구분 |
| 완료 판정 | JSON 형식 통과와 과제 수행 여부를 별도로 점검 |

위 항목은 원인 분석에서 확인한 수정 지점이며 적용한 새 프롬프트나 최종 연구 설계가 아니다. 이번 원인 점검에서는 추가 모델 호출 없이 원본 프롬프트·예측·수치를 보존했다.

## 작업 기록과 구현체

- [초안 PR #18](https://github.com/CalainKim/Trend_Verification_System/pull/18)
- [실제 프롬프트와 8건 출력 원인 분석](https://github.com/CalainKim/Trend_Verification_System/blob/codex/reasoning-paper-pilot/docs/research/QWEN_PROMPT_DIAGNOSIS.md)
- [실제 요청 문자열 사본](https://github.com/CalainKim/Trend_Verification_System/blob/codex/reasoning-paper-pilot/docs/research/pilot-prompt-v1.json)
- [환경·비용·기존 집계 기록](https://github.com/CalainKim/Trend_Verification_System/blob/codex/reasoning-paper-pilot/docs/research/RESULTS.md)
- [재현 실행 안내](https://github.com/CalainKim/Trend_Verification_System/blob/codex/reasoning-paper-pilot/docs/research/RUNBOOK.md)
- [편집 가능한 draw.io 실행 흐름](https://github.com/CalainKim/Trend_Verification_System/blob/codex/reasoning-paper-pilot/docs/research/research-flow.drawio)

기존 연구 질문·비교군·논문 메모는 저장소에 후보 초안으로 남긴다. 이번 주 공유 내용은 환경 구축과 스펙 점검, 발견한 과제 해석 문제까지로 한정한다.
