"""Offline contract checks; no real credentials, model requests, or sealed labels."""
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trend_research import runner as r
from trend_research.providers import ClaudeClient, ModelConfig, ProviderError


def config(tmp_path, **budget):
    data = json.loads(r.DEFAULT_CONFIG.read_text(encoding="utf-8"))
    data["budget"].update(budget)
    data["runtime"]["a40_started_at"] = datetime.now(timezone.utc).isoformat()
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class FakeClient:
    def __init__(self, model, calls, fail=False, invalid=False):
        self.model = model
        self.calls = calls
        self.fail = fail
        self.invalid = invalid

    def generate(self, system, user):
        self.calls.append((self.model, system, user))
        if self.fail:
            raise RuntimeError("an exception containing a pretend SECRET must not leak")
        return {"text": "bad-json" if self.invalid else json.dumps({
            "verdict": "HOLD", "summary": "근거만으로 지속을 판단하기 어렵다.",
            "support": [], "against": [], "unknowns": ["확인 구간은 보이지 않는다."]}),
            "actual_model": self.model, "finish_reason": "stop",
            "usage": {"input_tokens": 100, "output_tokens": 50}, "usage_complete": True}

    def close(self):
        pass


def factory(calls, **kw):
    return lambda cfg, root: FakeClient(cfg.model, calls, **kw)


def test_selected_provider_only_and_readiness_resumes_without_recall(tmp_path):
    cfg = config(tmp_path)
    # The unselected model need not even be configured.
    data = json.loads(cfg.read_text())
    data["models"]["a40"] = {"invalid": "not used"}
    cfg.write_text(json.dumps(data))
    calls = []
    store = tmp_path / "run"
    first = r.run(store, config_path=cfg, provider="claude", limit=1, client_factory=factory(calls))
    assert len(first["attempts"]) == len(calls) == 1
    assert {x["provider"] for x in first["records"].values()} == {"claude"}
    full = r.run(store, config_path=cfg, provider="claude", client_factory=factory(calls))
    assert len(full["attempts"]) == len(calls) == 8
    r.run(store, config_path=cfg, provider="claude", client_factory=factory(calls))
    assert len(calls) == 8
    assert all(x["status"] == "complete" for x in full["records"].values())


def test_both_models_receive_identical_prompts(tmp_path):
    calls = []
    state = r.run(tmp_path / "run", config_path=config(tmp_path), limit=1, client_factory=factory(calls))
    assert len(calls) == 2
    assert calls[0][1:] == calls[1][1:]
    records = list(state["records"].values())
    assert records[0]["input_hash"] == records[1]["input_hash"]
    assert records[0]["prompt_hash"] == records[1]["prompt_hash"]


def test_preflight_budget_rejects_before_network(tmp_path):
    calls = []
    state = r.run(tmp_path / "run", config_path=config(tmp_path, claude_usd=0.01),
                  provider="claude", client_factory=factory(calls))
    assert calls == []
    assert state["attempts"] == []
    assert all(x["status"] == "budget_skipped" for x in state["records"].values())


def test_failures_reserved_retry_explicit_capped_and_sanitized(tmp_path):
    cfg, store, calls = config(tmp_path), tmp_path / "run", []
    state = r.run(store, config_path=cfg, provider="claude", limit=1, client_factory=factory(calls, fail=True))
    record = next(iter(state["records"].values()))
    assert record["status"] == "failed" and record["error"] == "RuntimeError"
    assert "SECRET" not in json.dumps(state)
    assert state["attempts"][0]["accounted_claude_usd"] > 0
    r.run(store, config_path=cfg, provider="claude", limit=1, client_factory=factory(calls, fail=True))
    assert len(calls) == 1
    for _ in range(7):
        state = r.run(store, config_path=cfg, provider="claude", limit=1, retry=True,
                      client_factory=factory(calls, fail=True))
    assert len(calls) == 5
    assert sum(a["is_retry"] for a in state["attempts"]) == 4
    assert next(iter(state["records"].values()))["estimated_cost_usd"] == pytest.approx(r._charged(state))


def test_invalid_output_not_converted_to_hold(tmp_path):
    state = r.run(tmp_path / "run", config_path=config(tmp_path), provider="claude", limit=1,
                  client_factory=factory([], invalid=True))
    record = next(iter(state["records"].values()))
    assert record["status"] == "invalid" and record["result"] is None
    assert record["validation_errors"]


def test_actual_claude_cost_and_failure_recovery_aggregate(tmp_path):
    cfg, store = config(tmp_path), tmp_path / "run"
    r.run(store, config_path=cfg, provider="claude", limit=1, client_factory=factory([], fail=True))
    state = r.run(store, config_path=cfg, provider="claude", limit=1, retry=True, client_factory=factory([]))
    record = next(iter(state["records"].values()))
    assert record["status"] == "complete"
    assert state["attempts"][1]["actual_claude_usd"] == pytest.approx(0.0007)
    assert record["cost_usd"] is None  # Previous failure's actual bill is unknown.
    assert record["estimated_cost_usd"] > 0.0007
    assert record["elapsed_seconds"] >= record["last_attempt_elapsed_seconds"]


def test_live_other_views_and_excessive_limits_refused(tmp_path):
    with pytest.raises(ValueError, match="structured"):
        r.run(tmp_path / "run", input_view="history")
    with pytest.raises(ValueError, match="ceiling"):
        r.run(tmp_path / "run", provider="claude", config_path=config(tmp_path, claude_usd=3))


def test_a40_timer_must_be_actual_and_cannot_be_reset(tmp_path):
    cfg, store = config(tmp_path), tmp_path / "run"
    state = r.run(store, config_path=cfg, provider="a40", limit=1, client_factory=factory([]))
    data = json.loads(cfg.read_text())
    data["runtime"]["a40_started_at"] = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()
    cfg.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="reset"):
        r.run(store, config_path=cfg, provider="a40", client_factory=factory([]))
    data["runtime"]["a40_started_at"] = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    cfg.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="cap"):
        r.run(tmp_path / "expired", config_path=cfg, provider="a40", client_factory=factory([]))


def test_freeze_is_required_before_any_label_read(tmp_path, monkeypatch):
    labels = tmp_path / "pretend-labels.json"
    original = Path.read_text
    def guarded(path, *args, **kwargs):
        assert path != labels, "labels must not be read before freeze"
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", guarded)
    with pytest.raises(FileNotFoundError):
        r.score_run(tmp_path / "missing-run", labels)


def test_frozen_prediction_tamper_and_label_digest_mismatch_rejected(tmp_path):
    cfg, store = config(tmp_path), tmp_path / "run"
    r.run(store, config_path=cfg, provider="claude", limit=1, client_factory=factory([]))
    frozen = r.freeze(store)
    assert r.freeze(store)["prediction_sha256"] == frozen["prediction_sha256"]
    fake_labels = tmp_path / "fake-labels.json"
    fake_labels.write_text('{"labels":{}}', encoding="utf-8")
    with pytest.raises(ValueError, match="Label seal"):
        r.score_run(store, fake_labels)
    with pytest.raises(ValueError, match="frozen"):
        r.run(store, config_path=cfg, provider="claude", client_factory=factory([]))
    state = json.loads((store / "state.json").read_text(encoding="utf-8"))
    next(iter(state["records"].values()))["result"]["verdict"] = "WATCH"
    r.atomic_json(store / "state.json", state)
    with pytest.raises(ValueError, match="changed"):
        r.score_run(store, fake_labels)


def test_scoring_synthetic_test_labels_after_matching_seal(tmp_path):
    # Only newly constructed test labels are used; repository sealed labels are
    # never opened by this test or this implementation task.
    cfg, store = config(tmp_path), tmp_path / "run"
    state = r.run(store, config_path=cfg, provider="claude", client_factory=factory([]))
    truth = {cid: "persist" if i % 2 else "fade" for i, cid in enumerate(state["expected_case_ids"])}
    raw = json.dumps({"labels": truth}, sort_keys=True)
    state["expected_label_digest"] = hashlib.sha256(raw.encode()).hexdigest()
    r.atomic_json(store / "state.json", state)
    r.freeze(store)
    labels = tmp_path / "synthetic-labels.json"
    labels.write_text(raw, encoding="utf-8")
    report = r.score_run(store, labels)
    claude = next(c for c in report["cards"] if c["provider"] == "claude")
    assert claude["n_hold"] == 8 and claude["n_failed"] == 0
    assert claude["answered_accuracy"] is None
    assert len(report["cards"]) == 5  # Claude plus four no-cost baselines; no invented A40 result.
    output = r.export_run(store)
    assert output["providers"] == ["claude"]
    assert (Path(output["output_dir"]) / "comparison.csv").exists()


def test_demo_never_calls_provider_or_scores_as_real(tmp_path):
    def forbidden(*args):
        raise AssertionError("network forbidden")
    store = tmp_path / "demo"
    state = r.run(store, config_path=config(tmp_path), demo=True, limit=1, client_factory=forbidden)
    assert state["demo"] and all(a["accounted_claude_usd"] == 0 for a in state["attempts"])
    r.freeze(store)
    with pytest.raises(ValueError, match="Synthetic"):
        r.score_run(store, tmp_path / "does-not-exist.json")


def test_claude_effort_is_actually_sent_without_temperature():
    captured = {}
    def create(**kwargs):
        captured.update(kwargs)
        return {"content": [{"type": "text", "text": "{}"}], "model": "claude-sonnet-5-5",
                "stop_reason": "end_turn", "usage": {"input_tokens": 1, "output_tokens": 1}}
    sdk = SimpleNamespace(messages=SimpleNamespace(create=create))
    client = ClaudeClient(ModelConfig(provider="anthropic", model="claude-sonnet-5-5", temperature=None,
                                      effort="low"), ROOT, sdk_client=sdk)
    client.generate("s", "u")
    assert captured["output_config"] == {"effort": "low"}
    assert "temperature" not in captured


def test_response_model_mismatch_is_invalid_and_still_charged(tmp_path):
    state = r.run(tmp_path / "run", config_path=config(tmp_path), provider="claude", limit=1,
                  client_factory=lambda cfg, root: FakeClient("different-model", []))
    record = next(iter(state["records"].values()))
    assert record["status"] == "invalid" and record["result"] is None
    assert "response_model_mismatch" in record["validation_errors"]
    assert r._charged(state) == pytest.approx(0.0007)


def test_retry_usage_accumulates_without_losing_incomplete_usage(tmp_path):
    cfg, store = config(tmp_path), tmp_path / "run"
    r.run(store, config_path=cfg, provider="claude", limit=1, client_factory=factory([], invalid=True))
    state = r.run(store, config_path=cfg, provider="claude", limit=1, retry=True, client_factory=factory([]))
    record = next(iter(state["records"].values()))
    assert record["usage"] == {"input_tokens": 200, "output_tokens": 100}
    assert record["usage_complete"] is True
    assert record["last_attempt_usage"] == {"input_tokens": 100, "output_tokens": 50}
    assert all(attempt["usage_complete"] for attempt in state["attempts"])


def test_a40_requires_full_request_timeout_headroom(tmp_path):
    cfg = config(tmp_path)
    data = json.loads(cfg.read_text())
    data["runtime"]["a40_started_at"] = (datetime.now(timezone.utc) - timedelta(seconds=7000)).isoformat()
    cfg.write_text(json.dumps(data))
    calls = []
    with pytest.raises(ValueError, match="cap"):
        r.run(tmp_path / "run", config_path=cfg, provider="a40", client_factory=factory(calls))
    assert calls == []


def test_total_budget_keeps_a40_cost_on_claude_only_resume(tmp_path):
    cfg, store, calls = config(tmp_path, total_usd=1.75), tmp_path / "run", []
    r.run(store, config_path=cfg, provider="a40", limit=1, client_factory=factory(calls))
    assert len(calls) == 1
    state = r.run(store, config_path=cfg, provider="claude", limit=1, client_factory=factory(calls))
    assert len(calls) == 1
    claude = next(x for x in state["records"].values() if x["provider"] == "claude")
    assert claude["status"] == "budget_skipped" and claude["error"] == "total_budget"
    assert r.export_run(store)["providers"] == ["a40"]


@pytest.mark.parametrize("field,value", [("model", "Qwen/Qwen3-4B"), ("enable_thinking", False), ("temperature", 0.1)])
def test_qwen_contract_cannot_silently_change(tmp_path, field, value):
    cfg = config(tmp_path)
    data = json.loads(cfg.read_text())
    data["models"]["a40"][field] = value
    cfg.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Qwen"):
        r.run(tmp_path / "run", config_path=cfg, provider="a40", client_factory=factory([]))


def test_provider_error_keeps_http_status_not_private_body():
    class MockAPIError(Exception):
        status_code = 401
    def create(**kwargs):
        raise MockAPIError("secret-key-and-private-body")
    sdk = SimpleNamespace(messages=SimpleNamespace(create=create))
    client = ClaudeClient(ModelConfig(provider="anthropic", model="claude-sonnet-5-5", temperature=None,
                                      effort="low"), ROOT, sdk_client=sdk)
    with pytest.raises(ProviderError) as caught:
        client.generate("s", "u")
    assert "HTTP 401" in str(caught.value) and "MockAPIError" in str(caught.value)
    assert "secret" not in str(caught.value)
