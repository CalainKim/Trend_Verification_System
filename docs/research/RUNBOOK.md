# 맨투맨 연구 실행 안내

기존 사이트 없이 `scripts/run_reasoning_smoke.py`로 실행한다. 연구 질문·대상·해석은 [PROTOCOL.md](PROTOCOL.md), 실제 완료 범위는 [RESULTS.md](RESULTS.md)에 둔다.

## 준비와 입력 확인

저장소 루트에서 Python 3.11 이상을 사용한다. PC에는 API 실행기만 설치한다. GPU 모델 서버는 A40에 별도로 준비한다.

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-research.txt
.venv/Scripts/python -m pytest tests/test_research_inputs.py tests/test_research_evaluation.py tests/test_research_runner.py -q
.venv/Scripts/python scripts/run_reasoning_smoke.py preview --input-view static --output-dir private/research-preview
.venv/Scripts/python scripts/run_reasoning_smoke.py preview --input-view history --output-dir private/research-preview
.venv/Scripts/python scripts/run_reasoning_smoke.py preview --input-view structured --output-dir private/research-preview
```

Windows 임시 폴더 권한 오류가 있으면 pytest에 `--basetemp C:/Users/yaburi/.codex/tmp/research-check-<새이름>`을 붙인다. preview는 모델을 호출하지 않는다. 자료는 고정된 8개 사례와 해시가 맞아야 읽힌다. 원본 본문을 그대로 전달하지 않고 허용된 순위 자료만 새로 구성한다.

합성 출력으로 저장·재개·출력 형식만 확인할 수 있다. 실제 실험과 저장소를 분리하며 합성 실행은 채점할 수 없다.

```powershell
.venv/Scripts/python scripts/run_reasoning_smoke.py run --demo --provider both --input-view structured --store private/research-pilot/demo
.venv/Scripts/python scripts/run_reasoning_smoke.py export --store private/research-pilot/demo
```

## 실제 모델 실행

`.env`에 `ANTHROPIC_API_KEY`를 두거나 환경 변수로 제공한다. 키가 다른 작업 폴더에 있으면 `--credentials-root <그 폴더>`로 지정한다. 키를 설정 JSON이나 Git에 넣지 않는다.

`configs/research-pilot.example.json`을 `private/research-pilot/config.json`으로 복사한다. 실제 모델 revision, 서버 버전, 컨테이너 이미지와 GPU 임대 시작 시각을 기록한다. `a40_started_at`은 **모델 요청 시작이 아니라 유료 Pod 시작 시각**이다. 재시도 시 초기화하지 않는다. 실제 표시된 시간당 가격을 사용한다.

Claude만 먼저 실행할 수 있다. 처음 1건은 전체 8건에 포함하며, 같은 저장소로 이어 실행하면 정상 완료 결과를 다시 호출하지 않는다.

```powershell
.venv/Scripts/python scripts/run_reasoning_smoke.py run --provider claude --limit 1 --store private/research-pilot/live --config private/research-pilot/config.json
.venv/Scripts/python scripts/run_reasoning_smoke.py run --provider claude --store private/research-pilot/live --config private/research-pilot/config.json
```

A40에는 공식 Qwen3-8B 가중치와 vLLM을 사용한다. 모델 서버는 원격 `127.0.0.1`에 바인딩하고 SSH 터널로 연결한다. 학습·외부 공개 API는 만들지 않는다. 이번 확인 환경은 `runpod/pytorch:1.5.0-cu1281-torch280-ubuntu2404`, Python 3.12.3, PyTorch 2.8.0이다.

```bash
uv venv --system-site-packages /tmp/trend-vllm-env
uv pip install --python /tmp/trend-vllm-env/bin/python vllm==0.10.2 transformers==4.57.6 huggingface-hub==0.36.2
HF_HOME=/workspace/trend-models/huggingface HF_HUB_DISABLE_IMPLICIT_TOKEN=1 VLLM_NO_USAGE_STATS=1 DO_NOT_TRACK=1 OMP_NUM_THREADS=4 /tmp/trend-vllm-env/bin/vllm serve Qwen/Qwen3-8B --revision b968826d9c46dd6066d109eabc6255188de91218 --host 127.0.0.1 --port 8000 --dtype bfloat16 --max-model-len 16384 --max-num-seqs 1 --gpu-memory-utilization 0.85 --reasoning-parser qwen3 --download-dir /workspace/trend-models/huggingface --disable-log-requests
```

실제 요청은 thinking을 켜고 temperature 0.6을 전달했다. 모델 기본값 top_p 0.95·top_k 20과 서버 기본값 min_p 0·반복 페널티 1을 사용했다. 엔진 seed는 0이며 요청 seed는 별도로 지정하지 않았다. 패키지·컴파일 캐시는 컨테이너 초기화 시 사라지고 `/workspace`의 가중치만 보존된다. 같은 입력의 반복 호출이 완전히 결정적이라고 가정하지 않는다.

Runpod Connect에 실제로 표시된 호스트·포트와 기존 SSH 키로 연결한다. 아래의 대괄호 자리는 현재 연결 정보로 바꾼다. 이전 화면의 IP를 재사용하지 않는다.

```powershell
ssh -N -L 18000:127.0.0.1:8000 -p <현재포트> -i <기존키경로> root@<현재호스트>
.venv/Scripts/python scripts/run_reasoning_smoke.py run --provider a40 --store private/research-pilot/live --config private/research-pilot/config.json
```

두 모델이 준비되어 있으면 `--provider both`도 가능하다. 실패를 조사한 다음에만 `--retry`를 사용한다. 정상 완료 건은 재실행하지 않는다. 합계 기본 16회·실패 복구 4회, Claude $2·전체 $5·A40 2시간 상한을 적용한다. A/B의 실제 호출은 이번 실행기에서 차단하며 preview만 허용한다.

API 사용량이 확인되지 않은 실패는 요청의 보수적 최대 비용을 예산에서 소비한 것으로 남긴다. 실제 과금액과 이 예약액은 같은 값으로 보고하지 않는다. A40 비용은 추론 시간 외에도 준비·모델 다운로드·대기 시간을 포함한다.

**실행기 종료는 Runpod 중지가 아니다.** 2시간 이내에 Pod를 직접 중지하고 중지 시각·실제 임대액을 기록한다. 실험이 먼저 끝나면 즉시 중지한다. Global volume은 중지 이후에도 보관료가 발생할 수 있다. 네트워크 연결이나 로그인에 막혔다면 미실행으로 남기고 결과를 만들어 넣지 않는다.

## 예측 봉인 후 채점

모델 호출과 허용된 실패 복구가 모두 끝난 다음 진행한다. 부분 실행을 봉인하면 그 저장소에서 모델 호출을 더 할 수 없다. A40가 미실행이면 먼저 보류 상태를 확인하고, 나중에 채점 결과를 본 상태에서 같은 개발 사례의 예측을 추가하지 않는다.

```powershell
.venv/Scripts/python scripts/run_reasoning_smoke.py freeze --store private/research-pilot/live
.venv/Scripts/python scripts/load_snapshots.py
.venv/Scripts/python scripts/build_persistence_cases.py --source commerce --step 21 --no-seasonality --out private/research-labels
.venv/Scripts/python scripts/run_reasoning_smoke.py score --store private/research-pilot/live --labels private/research-labels/labels.sealed.json
.venv/Scripts/python scripts/run_reasoning_smoke.py export --store private/research-pilot/live
```

기존 도구로 복원한 정답 전체의 해시가 `benchmark/labels.digest.txt`와 일치해야 채점된다. 불일치하면 라벨·문턱·대상을 맞춰 바꾸지 않고 원인을 조사한다. 예측 해시도 다시 검사하므로 봉인 이후 예측을 수정할 수 없다.

`private/research-pilot/live/export`에 JSON 기록, 비교 CSV, 보고서와 채점표가 나온다. 원본 응답·실패·프롬프트 해시·실제 모델 ID·사용량을 보존한다. 공개 문서에는 필요한 결과와 출력 예시만 선별한다. 정답 파일과 키는 올리지 않는다.

## 이번 결과의 해석

C와 단순 기준선의 예비 수치만 해석한다. A/B/C 효과, 시간 일반화, 학습 효과는 아직 측정하지 않았다. 전체 정답·오답·보류·실패 비율과 답변율을 함께 읽고, 근거 ID가 맞는 것을 설명 내용 전체가 참이라는 뜻으로 해석하지 않는다. 논문 초안은 [PAPER_DRAFT.md](PAPER_DRAFT.md)에서 이어간다.

## forecast-v2: 같은 Qwen 8건의 과제 수행 확인

현재 결정한 예측·보류 규칙은 [FORECAST_V2.md](FORECAST_V2.md)에 있다. v1은 기본값으로 보존하며, 새 버전은 명시적으로 선택한다. 동일한 사용자 JSON에 시스템 지시만 바뀐다.

```powershell
python scripts/run_reasoning_smoke.py preview --prompt-version forecast-v2 --input-view structured --output-dir private/research-preview-v2
python scripts/run_reasoning_smoke.py run --provider a40 --prompt-version forecast-v2 --input-view structured --config private/research-pilot/config-v2.json --store private/research-pilot/forecast-v2
python scripts/run_reasoning_smoke.py freeze --store private/research-pilot/forecast-v2
```

이 실행에서는 `score`를 호출하지 않는다. 미래값 부재로 중단하는지, 문턱을 관측값처럼 쓰는지, 실제 과거 근거로 예측 또는 허용된 HOLD를 설명하는지만 점검한다. 평가 정답과 정확도 비교는 이번 목적에 포함하지 않는다.

새 store를 쓰더라도 예산이 새로 생기는 것은 아니다. config-v2는 기존 Claude·GPU 사용 추정을 총 $5에서 차감한 잔여액을 사용하고, 추가 호출 8회·재시도 0회·이번 GPU 세션 1,800초로 제한했다. 기존 GPU 886초와 합쳐 7,200초 안이다. 시간은 서버 준비·다운로드·대기까지 포함한 재시작 전 시각으로 기록하고 Pod 자체를 기한 안에 중지해야 한다.

재실행의 환경 차이(호스트 이전, 캐시 복구 등)와 실제 종료 시각은 별도 비용·환경 기록으로 남긴다. 원본 v1 결과나 프롬프트를 덮어쓰지 않으며, 버전이 다른 저장소 재개는 실행기가 거부한다.
