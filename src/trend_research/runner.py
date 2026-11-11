"""Small, resumable experiments with an explicit spend ledger and sealed scoring.

Prediction code never accepts labels. Scoring opens a label file only after a
frozen, unchanged prediction snapshot has been verified against its digest.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import fields
from datetime import datetime, timezone
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import time
import uuid

from .inputs import PROMPT_VERSIONS, baseline_predictions, build_prompt, load_cases, load_manifest, prepare_case
from .evaluation import evaluate, validate_result
from .providers import ModelConfig, ProviderError, create_client

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "configs/research-pilot.example.json"
MAX_INITIAL_CALLS = 16
MAX_RETRIES = 4
MAX_CLAUDE_USD = 2.0
MAX_TOTAL_USD = 5.0
MAX_A40_SECONDS = 7200
VIEWS = ("static", "history", "structured")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def _load(path):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError("Duplicate JSON key")
            out[key] = value
        return out
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def store_lock(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    lock = folder / ".runner.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError("Another runner owns this store; inspect a stale lock before removing it.") from None
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(str(os.getpid()))
        yield
    finally:
        lock.unlink(missing_ok=True)


def selected_providers(provider):
    if provider == "both":
        return ["claude", "a40"]
    if provider not in ("claude", "a40"):
        raise ValueError("provider must be claude, a40, or both")
    return [provider]


def settings(path, selected):
    data = _load(path)
    configs = {}
    names = {f.name for f in fields(ModelConfig)}
    for name in selected:
        raw = data.get("models", {}).get(name)
        if not isinstance(raw, dict) or set(raw) - names:
            raise ValueError("Invalid selected model configuration")
        config = ModelConfig(**raw)
        expected = "anthropic" if name == "claude" else "openai_compatible"
        if config.provider != expected or config.max_tokens > 8192 or config.timeout_seconds > 300:
            raise ValueError("Provider or output token cap differs from the pilot contract")
        if name == "claude" and (config.model != "claude-sonnet-5-5" or config.effort != "low"
                                 or config.input_price_per_million != 2
                                 or config.output_price_per_million != 10):
            raise ValueError("This pilot requires Sonnet 5.5, low effort, and its verified $2/$10 rates")
        if name == "a40" and (config.model != "Qwen/Qwen3-8B" or config.enable_thinking is not True
                              or config.temperature != 0.6):
            raise ValueError("This pilot requires Qwen/Qwen3-8B, thinking enabled, and temperature 0.6")
        configs[name] = config
    budget = data.get("budget", {})
    limits = {"claude_usd": MAX_CLAUDE_USD, "total_usd": MAX_TOTAL_USD,
              "initial_calls": MAX_INITIAL_CALLS, "retry_calls": MAX_RETRIES,
              "a40_seconds": MAX_A40_SECONDS}
    for key, ceiling in limits.items():
        value = budget.get(key, ceiling)
        if (type(value) not in (int, float) or not math.isfinite(value) or value < 0
                or (value == 0 and key != "retry_calls") or value > ceiling):
            raise ValueError("Budget must remain within the approved pilot ceiling")
        if key.endswith("calls") and type(value) is not int:
            raise ValueError("Call limits must be integers")
        limits[key] = value
    return configs, limits, data.get("runtime", {})


def _sealed_digest(repo_root):
    parts = (Path(repo_root) / "benchmark/labels.digest.txt").read_text(encoding="utf-8-sig").splitlines()
    values = dict(line.split(maxsplit=1) for line in parts if line.strip())
    value = values.get("sha256", "")
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("Missing or malformed source label digest")
    return value


def _state(folder, manifest, bundles, limits, repo_root, demo, prompt_version):
    path = folder / "state.json"
    if path.exists():
        state = _load(path)
        if state["manifest_hash"] != digest(manifest) or state["demo"] != demo or state["limits"] != limits:
            raise ValueError("Store identity, manifest, or budget changed; do not mix experiments")
        if state.get("prompt_version", "pilot-v1") != prompt_version:
            raise ValueError("Store prompt version changed; use a separate store for the new prompt")
        return state
    baselines = []
    for bundle in bundles:
        case_id = prepare_case(bundle, "static")["case_id"]
        for method, verdict in baseline_predictions(bundle).items():
            baselines.append({"case_id": case_id, "provider": method, "input_view": "baseline",
                              "status": "complete", "result": {"verdict": verdict},
                              "elapsed_seconds": 0.0, "cost_usd": 0.0})
    state = {"schema_version": 1, "created_at": now(), "demo": demo, "prompt_version": prompt_version,
             "manifest": manifest, "manifest_hash": digest(manifest),
             "expected_case_ids": [prepare_case(x, "static")["case_id"] for x in bundles],
             "expected_label_digest": _sealed_digest(repo_root), "limits": limits,
             "records": {}, "attempts": [], "baseline_records": baselines,
             "runtime_sessions": [], "notes": [
                 "Development pilot; one historical cutoff; correlated products.",
                 "Only the explicitly executed views are evidence. A/B/C effect is not established."]}
    atomic_json(path, state)
    return state


def _charged(state):
    return sum(a.get("accounted_claude_usd", 0.0) for a in state["attempts"])


def reservation(config, system, user):
    if config.provider != "anthropic":
        return 0.0
    # UTF-8 bytes plus ample request framing conservatively overestimate token
    # counts; no caching discount is assumed. Output includes thinking tokens.
    tokens = len(system.encode("utf-8")) + len(user.encode("utf-8")) + 1024
    return (tokens * config.input_price_per_million + config.max_tokens * config.output_price_per_million) / 1_000_000


def usage_cost(config, response):
    if config.provider != "anthropic" or not response.get("usage_complete"):
        return None
    usage = response.get("usage", {})
    if any(type(usage.get(k)) is not int or usage[k] < 0 for k in ("input_tokens", "output_tokens")):
        return None
    return (usage["input_tokens"] * config.input_price_per_million
            + usage["output_tokens"] * config.output_price_per_million) / 1_000_000


def _gpu_bound(runtime, limits, required_seconds=0):
    """Return elapsed rental bound. Caller must stop the Pod, not just inference."""
    started = runtime.get("a40_started_at")
    if not started:
        raise ValueError("Record actual a40_started_at (UTC ISO timestamp) before a live A40 call")
    dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("a40_started_at requires a timezone")
    elapsed = (datetime.now(timezone.utc) - dt).total_seconds()
    if elapsed < -5 or elapsed + required_seconds >= limits["a40_seconds"]:
        raise ValueError("A40 rental time cap reached or start time is invalid; stop the Pod")
    rate = runtime.get("a40_hourly_usd")
    if type(rate) not in (int, float) or not math.isfinite(rate) or not 0 < rate <= 1:
        raise ValueError("Record the actual A40 hourly price (pilot ceiling $1/hr)")
    # Reserve the entire permitted session, not just active generation seconds.
    return limits["a40_seconds"] / 3600 * rate


def _demo_response(prepared, config):
    return {"text": canonical({"verdict": "HOLD", "summary": "합성 응답: 저장 경로만 확인합니다.",
                               "support": [], "against": [], "unknowns": ["실제 모델을 호출하지 않았습니다."]}),
            "actual_model": "demo:" + config.model, "finish_reason": "stop", "usage": {}, "usage_complete": False}


def run(store, *, repo_root=ROOT, manifest_path=None, config_path=DEFAULT_CONFIG,
        provider="both", input_view="structured", credentials_root=None, limit=None,
        retry=False, demo=False, prompt_version="pilot-v1", client_factory=create_client):
    if input_view not in VIEWS:
        raise ValueError("Unknown input view")
    if prompt_version not in PROMPT_VERSIONS:
        raise ValueError("Unknown prompt version")
    if not demo and prompt_version == "forecast-v2" and provider != "a40":
        raise ValueError("The forecast-v2 follow-up authorizes Qwen/a40 only")
    if not demo and input_view != "structured":
        raise ValueError("This $5 pilot authorizes live structured view only; preview A/B without paid calls")
    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError("limit must be positive")
    manifest = load_manifest(manifest_path, repo_root=Path(repo_root))
    bundles = load_cases(manifest, Path(repo_root))
    selected = selected_providers(provider)
    configs, limits, runtime = settings(config_path, selected)
    folder = Path(store)
    with store_lock(folder):
        if (folder / "frozen.json").exists():
            raise ValueError("Predictions are frozen; this store cannot generate more predictions")
        state = _state(folder, manifest, bundles, limits, repo_root, demo, prompt_version)
        if not demo and "a40" in selected:
            gpu_bound = _gpu_bound(runtime, limits)
            prior_start = state.get("a40_started_at")
            if prior_start and prior_start != runtime["a40_started_at"]:
                raise ValueError("Do not reset the pilot's two-hour A40 rental clock")
            state["a40_started_at"] = runtime["a40_started_at"]
            state["a40_reserved_usd"] = max(state.get("a40_reserved_usd", 0.0), gpu_bound)
        storage_reserve = runtime.get("storage_reserve_usd", 0.5)
        if type(storage_reserve) not in (int, float) or not math.isfinite(storage_reserve) or storage_reserve < 0:
            raise ValueError("Invalid storage cost reserve")
        state["storage_reserved_usd"] = max(state.get("storage_reserved_usd", 0.0), storage_reserve)
        session = {"started_at": now(), "providers": selected, "input_view": input_view, "prompt_version": prompt_version,
                   "runtime": runtime, "models": {k: v.public_dict() for k, v in configs.items()}}
        state["runtime_sessions"].append(session)
        atomic_json(folder / "state.json", state)
        clients = {}
        try:
            for bundle in bundles[:limit]:
                prepared = prepare_case(bundle, input_view)
                system, user = build_prompt(prepared, prompt_version)
                for name in selected:
                    config = configs[name]
                    key = prepared["case_id"] + "|" + name + "|" + input_view
                    cache_hash = digest({"system": system, "user": user, "model": config.public_dict(), "demo": demo})
                    previous = state["records"].get(key)
                    if previous and previous["cache_hash"] != cache_hash:
                        raise ValueError("Existing case prompt/model changed; do not overwrite the experiment")
                    if previous and previous["status"] == "complete":
                        continue
                    tried = [a for a in state["attempts"] if a["key"] == key]
                    if tried and not retry:
                        continue
                    is_retry = bool(tried)
                    initial_count = sum(not a["is_retry"] for a in state["attempts"])
                    retry_count = sum(a["is_retry"] for a in state["attempts"])
                    reserve = 0.0 if demo else reservation(config, system, user)
                    reason = None
                    if (not is_retry and initial_count >= limits["initial_calls"]) or (is_retry and retry_count >= limits["retry_calls"]):
                        reason = "approved_call_limit"
                    elif _charged(state) + reserve > limits["claude_usd"] + 1e-12:
                        reason = "claude_budget"
                    if not demo and "a40" in selected:
                        # Reserve connection timeout, read timeout and a shutdown
                        # margin. The independent Pod deadline remains required.
                        _gpu_bound(runtime, limits, config.timeout_seconds + min(15, config.timeout_seconds) + 10)
                    if not demo and (_charged(state) + reserve + state.get("a40_reserved_usd", 0.0)
                                     + state["storage_reserved_usd"] > limits["total_usd"]):
                        reason = "total_budget"
                    if reason:
                        if not previous:
                            state["records"][key] = {"case_id": prepared["case_id"], "provider": name,
                                                     "input_view": input_view, "status": "budget_skipped",
                                                     "result": None, "cache_hash": cache_hash, "error": reason}
                        atomic_json(folder / "state.json", state)
                        continue
                    attempt = {"key": key, "provider": name, "is_retry": is_retry, "started_at": now(), "status": "inflight",
                               "reserved_claude_usd": reserve, "accounted_claude_usd": reserve,
                               "actual_claude_usd": None}
                    state["attempts"].append(attempt)
                    record = {"case_id": prepared["case_id"], "provider": name, "input_view": input_view,
                              "prompt_version": prompt_version,
                              "status": "interrupted", "result": None, "cache_hash": cache_hash,
                              "input_hash": digest(prepared), "prompt_hash": digest([system, user]),
                              "prepared_input": prepared, "prompt": {"system": system, "user": user},
                              "model_config": config.public_dict(), "demo": demo,
                              "attempt_number": len(tried) + 1, "started_at": attempt["started_at"]}
                    state["records"][key] = record
                    atomic_json(folder / "state.json", state)  # Reservation survives interruption.
                    started = time.monotonic()
                    try:
                        if demo:
                            response = _demo_response(prepared, config)
                        else:
                            if name not in clients:
                                clients[name] = client_factory(config, credentials_root or repo_root)
                            response = clients[name].generate(system, user)
                        checked = validate_result(response["text"], prepared, response.get("finish_reason"))
                        if not demo and response.get("actual_model") != config.model:
                            checked.update(status="invalid", result=None)
                            checked["errors"].append("response_model_mismatch")
                        attempt["usage"] = response.get("usage", {})
                        attempt["usage_complete"] = response.get("usage_complete") is True
                        record.update({"status": checked["status"], "result": checked["result"],
                                       "validation_errors": checked["errors"], "warnings": checked.get("warnings", []),
                                       "numeric_flags": checked.get("numeric_flags", []), "response": response,
                                       "actual_model": response.get("actual_model"), "usage": response.get("usage", {})})
                        actual = None if demo else usage_cost(config, response)
                        if name == "claude" and not demo:
                            attempt["actual_claude_usd"] = actual
                            attempt["accounted_claude_usd"] = actual if actual is not None else reserve
                            record["cost_usd"] = actual
                            record["budget_reservation_usd"] = reserve if actual is None else 0.0
                        elif demo:
                            record["cost_usd"] = 0.0
                    except Exception as exc:
                        record.update({"status": "failed", "result": None,
                                       "error": str(exc) if isinstance(exc, ProviderError) else type(exc).__name__})
                    finally:
                        attempt["elapsed_seconds"] = round(time.monotonic() - started, 6)
                        case_attempts = [a for a in state["attempts"] if a["key"] == key]
                        record["last_attempt_usage"] = attempt.get("usage", {})
                        record["usage"] = {field: sum(a.get("usage", {}).get(field, 0) for a in case_attempts)
                                           for field in ("input_tokens", "output_tokens")
                                           if any(field in a.get("usage", {}) for a in case_attempts)}
                        record["usage_complete"] = all(a.get("usage_complete", False) for a in case_attempts)
                        record["last_attempt_elapsed_seconds"] = attempt["elapsed_seconds"]
                        record["elapsed_seconds"] = round(sum(a.get("elapsed_seconds", 0.0) for a in case_attempts), 6)
                        if name == "claude" and not demo:
                            actual_costs = [a.get("actual_claude_usd") for a in case_attempts]
                            record["cost_usd"] = sum(actual_costs) if all(x is not None for x in actual_costs) else None
                            if record["cost_usd"] is None:
                                record["estimated_cost_usd"] = sum(a["accounted_claude_usd"] for a in case_attempts)
                        record["finished_at"] = now()
                        attempt["status"] = record["status"]
                        attempt["finished_at"] = record["finished_at"]
                        atomic_json(folder / "state.json", state)
        finally:
            for client in clients.values():
                client.close()
            session["finished_at"] = now()
            atomic_json(folder / "state.json", state)
        return state


def _prediction_payload(state):
    return {key: state[key] for key in ("schema_version", "demo", "prompt_version", "manifest", "manifest_hash", "expected_case_ids",
                                      "expected_label_digest", "limits", "records", "attempts", "baseline_records",
                                      "runtime_sessions", "storage_reserved_usd", "a40_started_at", "a40_reserved_usd")
            if key in state}


def freeze(store):
    folder = Path(store)
    with store_lock(folder):
        state = _load(folder / "state.json")
        if not state["records"]:
            raise ValueError("No predictions to freeze")
        payload = _prediction_payload(state)
        snapshot = {"frozen_at": now(), "prediction_sha256": digest(payload), "predictions": payload}
        if (folder / "frozen.json").exists():
            return verified_freeze(folder)
        atomic_json(folder / "frozen.json", snapshot)
        return snapshot


def verified_freeze(store):
    folder = Path(store)
    frozen = _load(folder / "frozen.json")
    if frozen["prediction_sha256"] != digest(frozen["predictions"]):
        raise ValueError("Frozen prediction digest mismatch")
    if digest(_prediction_payload(_load(folder / "state.json"))) != frozen["prediction_sha256"]:
        raise ValueError("Predictions changed after freezing")
    return frozen


def score_run(store, labels_path, *, output=None):
    # This ordering is deliberate: no label bytes are accessed before verifying
    # an immutable prediction snapshot and the original benchmark commitment.
    frozen = verified_freeze(store)
    payload = frozen["predictions"]
    if payload["demo"]:
        raise ValueError("Synthetic transport checks are not real model scores")
    raw = Path(labels_path).read_text(encoding="utf-8")
    actual = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    if actual != payload["expected_label_digest"]:
        raise ValueError("Label seal does not match the source benchmark; scoring refused")
    labels = json.loads(raw)["labels"]
    groups = {}
    attempted_providers = {attempt["provider"] for attempt in payload["attempts"]}
    for record in list(payload["records"].values()) + payload["baseline_records"]:
        if record["input_view"] != "baseline" and record["provider"] not in attempted_providers:
            continue
        groups.setdefault((record["provider"], record["input_view"]), []).append(record)
    cards = []
    for (provider, view), records in sorted(groups.items()):
        card = evaluate(records, labels, payload["expected_case_ids"])
        cards.append({"provider": provider, "input_view": view, **card})
    report = {"scored_at": now(), "prediction_sha256": frozen["prediction_sha256"],
              "labels_sha256": actual, "cards": cards,
              "unattempted_providers": sorted({r["provider"] for r in payload["records"].values()} - attempted_providers),
              "notes": [
                  "Development pilot, one historical cutoff; not an independent temporal test.",
                  "A/B/C effects require the unexecuted comparison views; agreement is not accuracy.",
                  "A40 rental cost is session-level, not a per-token API fee."]}
    atomic_json(output or Path(store) / "scorecard.json", report)
    return report


def export_run(store, output=None):
    folder = Path(store)
    state = _load(folder / "state.json")
    destination = Path(output) if output else folder / "export"
    destination.mkdir(parents=True, exist_ok=True)
    records = list(state["records"].values())
    atomic_json(destination / "run.json", state)
    providers = sorted({a["provider"] for a in state["attempts"]})
    for provider in providers:
        for view in sorted({r["input_view"] for r in records if r["provider"] == provider}):
            verdicts = {r["case_id"]: r["result"] for r in records
                        if r["provider"] == provider and r["input_view"] == view and r["status"] == "complete"}
            atomic_json(destination / f"verdicts-{provider}-{view}.json", verdicts)
    columns = ["case_id", "provider", "input_view", "status", "verdict", "summary", "elapsed_seconds",
               "input_tokens", "output_tokens", "usage_complete", "cost_usd", "estimated_cost_usd", "input_hash", "validation_errors", "numeric_flags"]
    with (destination / "comparison.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for record in sorted(records, key=lambda x: (x["case_id"], x["provider"], x["input_view"])):
            row = {k: record.get(k) for k in columns}
            row.update({k: (record.get("result") or {}).get(k) for k in ("verdict", "summary")})
            row.update({k: record.get("usage", {}).get(k) for k in ("input_tokens", "output_tokens")})
            for key, value in row.items():
                if isinstance(value, (dict, list)):
                    row[key] = canonical(value)
                elif isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                    row[key] = "'" + value
            writer.writerow(row)
    attempt_label = "합성 응답 생성" if state["demo"] else "실제 요청 시도"
    lines = ["# 맨투맨 추론 예비 실험", "", "합성 실행 — 실제 모델 결과가 아니다." if state["demo"] else "실제 모델 호출 기록", "",
             f"- 실행된 공급자: {', '.join(providers) or '없음'}",
             f"- 기록: {len(records)}개 / {attempt_label}: {len(state['attempts'])}회",
             f"- Claude 예산 반영액: ${_charged(state):.6f} (미확인 응답은 상한 예약액 포함)",
             "- A40 임대 시간과 보관료는 별도 기록한다. 프로세스 종료가 Pod 중지는 아니다.",
             "- 한 시점의 개발 사례다. 정답 채점 전에는 정확도를 표시하지 않는다.", "",
             "| 사례 | 모델 | 구성 | 상태 | 판정 |", "|---|---|---|---|---|"]
    for record in records:
        verdict = (record.get("result") or {}).get("verdict", "—")
        lines.append(f"| {record['case_id']} | {record['provider']} | {record['input_view']} | {record['status']} | {verdict} |")
    if (folder / "scorecard.json").exists():
        report = _load(folder / "scorecard.json")
        frozen = verified_freeze(folder)
        if report.get("prediction_sha256") != frozen["prediction_sha256"]:
            raise ValueError("Scorecard belongs to different predictions")
        atomic_json(destination / "scorecard.json", report)
        percent = lambda value: "—" if value is None else f"{value:.1%}"
        money = lambda value: "—" if value is None else f"${value:.6f}"
        lines += ["", "## 봉인 정답 대조", "", "정답·오답·보류·실패의 분모는 전체 8개 사례다. 답한 사례의 정확도는 보류와 실패를 제외한다. —는 분모가 없거나 비용이 확인되지 않았음을 뜻한다.", "",
                  "| 방법 | 구성 | 정답 | 오답 | 보류 | 실패 | 답변율 | 답한 사례 정확도 | 지속 적중률 | 지속 재현율 |",
                  "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for card in report["cards"]:
            lines.append(f"| {card['provider']} | {card['input_view']} | {card['correct']}/{card['n_cases']} | {card['wrong']}/{card['n_cases']} | {card['n_hold']}/{card['n_cases']} | {card['n_failed']}/{card['n_cases']} | {percent(card['coverage'])} | {percent(card['answered_accuracy'])} | {percent(card['persist_precision'])} | {percent(card['persist_recall'])} |")
        lines += ["", "### 비용과 오류 기록", "", "실제 비용 총액은 모든 사례의 비용이 확인된 경우만 표시한다. 알려진 부분합과 예약액 포함 예산 반영액은 scorecard.json에 별도로 보존한다. A40 임대료는 세션 전체의 별도 기록이 필요하다.", "",
                  "| 방법 | 전체 실제 비용 | 실제 비용 확인 사례 | 예약 포함 예산 반영 총액 | 수치 확인 표시 | 잘못된 근거 ID |",
                  "|---|---:|---:|---:|---:|---:|"]
        for card in report["cards"]:
            lines.append(f"| {card['provider']} | {money(card['actual_cost_total_usd'])} | {card['actual_cost_record_count']}/{card['n_cases']} | {money(card['accounted_cost_total_usd'])} | {card['numeric_review_flag_count']} | {card['invalid_evidence_id_count']} |")
        lines += ["", "### 실제 결과별 예측", "", "실패는 의도적 보류에 합치지 않는다.", "",
                  "| 방법 | 실제 결과 | 지속 예측 | 소멸 예측 | 보류 | 기술 실패 |", "|---|---|---:|---:|---:|---:|"]
        for card in report["cards"]:
            for truth, label in (("persist", "지속"), ("fade", "소멸")):
                matrix = card["confusion"][truth]
                lines.append(f"| {card['provider']} | {label} | {matrix['WATCH']} | {matrix['NOT_SUPPORTED']} | {matrix['HOLD']} | {card['failures_by_truth'][truth]} |")
    (destination / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"output_dir": str(destination.resolve()), "records": len(records), "providers": providers,
            "claude_accounted_usd": _charged(state)}
