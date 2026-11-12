# 구현체와 실제 연구 준비의 구분

2026-11-12 · `candidate-verification-v1`

## 현재 경로

| 구성 | 위치 | 역할 |
|---|---|---|
| 입력·자료집 검사 | [inputs.py](../../../src/trend_verification_v1/inputs.py) | 후보·출처·시점·대상 확인, 동결 자료집 검색 |
| 조사 실행기 | [engine.py](../../../src/trend_verification_v1/engine.py) | 초기 제안·질의·별도 반증·최종 제안, 인용 검증과 기록 |
| 합성 응답 공급자 | [demo.py](../../../src/trend_verification_v1/demo.py) | 실제 모델 호출 없는 연결 점검 |
| CLI | [run_candidate_verification.py](../../../scripts/run_candidate_verification.py) | `demo`, `inspect-config`, `verify` |
| 입력 예제 | [candidate-verification](../../../data/examples/candidate-verification/) | 실제 시장 자료가 아닌 합성 후보·자료집·미검토 가설 |
| 로컬 결과 화면 | [build_candidate_report.py](../../../scripts/build_candidate_report.py), [serve_candidate_report.py](../../../scripts/serve_candidate_report.py) | 저장된 실행 기록을 읽어 단계·근거·판정 표시 |

이번 구현의 **실제 연구 사례 수는 0, 실제 모델 호출 수는 0**이다. 화면의 Claude/Qwen은 비교 칸의 이름이며 합성 응답을 실제 모델 출력으로 해석하지 않는다. 실험 설정 점검은 접속 성공이나 모델 실행이 아니다. 실제 실행 경로는 잠겨 있다.

합성 예제는 제공된 묶음의 관측이 독립 원출처에서 왔다는 초기 주장을 원본 대조로 반증하는 상황이다. 같은 원본의 재게시로 정정되면 **그 묶음의 독립성 주장**을 기각한다. 홍보가 있다는 이유만으로 스타일 전체의 유행을 기각하는 예제가 아니다.

## 로컬에서 확인하기

저장소 루트에서 기존 프로젝트 Python 환경으로 실행한다. 아래 명령은 모델이나 GPU를 가동하지 않는다.

```powershell
python scripts/run_candidate_verification.py demo
python scripts/build_candidate_report.py
python scripts/serve_candidate_report.py
```

마지막 명령이 표시하는 로컬 주소에서 저장 결과를 본다. 기본 주소는 `http://127.0.0.1:8774/`다. 종료는 터미널에서 Ctrl+C를 누른다. 화면은 별도 로컬 저장 기록 뷰어이며 기존 사이트에 배포하거나 수집기를 자동 연결한 기능이 아니다. 표시 전 기록의 해시를 확인한다. 화면은 읽기 전용이며 사람 최종 판단은 별도 [양식](forms/human-decision.template.json)에 기록한다.

설정의 형식과 실행 잠금을 확인하려면 다음 명령을 사용한다.

```powershell
python scripts/run_candidate_verification.py inspect-config
```

저장 기록의 무결성을 확인하려면 `demo`가 출력한 실제 run 폴더를 지정한다. 아래 `<run_id>`는 실행 결과의 ID로 바꾼다.

```powershell
python scripts/run_candidate_verification.py verify private/candidate-verification/<run_id>
```

명령을 성공했다는 사실은 JSON·근거 ID·저장 구조의 검사 결과다. 자료의 사실성, 인터뷰 효과, 논리적 타당성, 미래 유행의 검증 결과가 아니다.

## 저장 구조와 상태

각 실행 폴더에 입력·단계 요청·최종 응답·검색 결과·`run.json`을 보존하고 해시로 연결한다. 동일 실행의 기록을 덮어쓰지 않는다. 재실행은 새 run ID를 사용한다. `synthetic=true`로 합성 출처를 구분한다.

`status=complete`는 절차와 구조 검증의 완료다. `api_error`, `schema_error`는 저장된 실행의 기술 실패다. 잘못된 입력·설정은 실행 폴더 생성 전에 거부되고 CLI에서 `configuration_error`로 보고한다. final이 없거나 실패한 실행을 HOLD로 채우지 않는다. 반증 전후의 판정·수정 이유는 `revisions`, 실제 전달된 근거는 `evidence_considered`에서 확인한다. 인용 검사는 실제 제공된 근거 ID를 대상으로 한다.

원문 응답과 전송 메타데이터는 재현 기록이며 연구 집계와 분리한다. 모델 버전·생성 설정·최대 출력 길이를 비교 조건으로 고정한다. 별도 운영 기록은 [운영 제약](../OPERATIONS.md)을 유지한다.

## 실제 본 비교 전에 필요한 일

| 준비 | 완료 조건 |
|---|---|
| 인터뷰 해석 검토 | 원문 구간 대조, 가설 수정·제외·채택 기록, `reviewed`와 출처 확인 |
| 새 후보 선정 | 선정·제외 기준과 후보 가설을 결과 확인 전에 고정 |
| 당시 자료 수집 | 원문·시점·대상·출처 관계 확인, 미래 자료·라벨 제외 |
| 자료집 동결 | 초기 근거·검색 대상·정렬 규칙·해시 고정 |
| 사람 기준표 | 출력 전 두 사람의 사실·반대 근거·미확인 정보 표시와 합의 |
| 모델 실험 연결 | 실제 모델 revision·설정, 조건 격리, 실행 순서와 실패 처리 확인 |
| 본 평가 | 공통 출력 가림, 독립 판독, 최초 불일치·합의 분리, 사례별 비교 |

현재는 실제 수집과 모델 본 비교를 수행하지 않았다. 합성 예제를 실제 사례로 이름만 바꾸어 제출하거나 기존 상품 순위 실험을 새로운 실험으로 합산하지 않는다. 평가 설계는 [EVALUATION.md](EVALUATION.md), 처리 계약은 [SPEC.md](SPEC.md)를 따른다.
