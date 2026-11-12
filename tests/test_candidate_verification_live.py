"""No network: exercise real live guards with a deterministic transport double."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from trend_verification_v1.demo import ScriptedDemoClient, load_example
from trend_verification_v1.engine import BudgetLimitReached, run_case, verify_run
from trend_verification_v1.inputs import digest
from trend_verification_v1.live import (AUTH_VERSION, LEDGER, SOURCES, BudgetedClient,
                                        LiveLedger, audit_prior, read, run_live)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def setup(tmp_path):
    case, corpus, criteria = load_example(ROOT)
    # Transport tests use synthetic source data marked as such. A live call is
    # independent of data origin and must not turn synthetic data into study data.
    config = read(ROOT / "configs/candidate-verification.example.json")
    config["live_execution_enabled"] = True
    first_cost = read(ROOT / SOURCES[2])
    second_cost = read(ROOT / SOURCES[3])
    state = {"demo": False, "attempts": [{"provider": "claude", "actual_claude_usd": 0.10114,
             "accounted_claude_usd": 0.10114, "reserved_claude_usd": 0.15, "status": "complete"}],
             "storage_reserved_usd": 0.5, "a40_started_at": first_cost["session_started_at_conservative"]}
    second = {"demo": False, "attempts": [], "storage_reserved_usd": 0.5,
              "a40_started_at": second_cost["session_started_at_conservative"]}
    for name, value in zip(SOURCES, (state, second, first_cost, second_cost)):
        save(tmp_path / name, value)
    auth = {"schema_version": AUTH_VERSION, "authorization_id": "authorized-test",
            "authorized_at": datetime.now(timezone.utc).isoformat(), "max_stage_calls": 20,
            "max_recovery_calls": 0, "source_hashes": audit_prior(tmp_path)["source_hashes"],
            "input_hashes": {"case": digest(case), "corpus": digest(corpus), "criteria": digest(criteria)},
            "config_hash": digest(config), "storage_reserve_usd": 0.5, "rental_path": "private/rental.json"}
    return tmp_path, (case, corpus, criteria), config, auth


class Factory:
    def __init__(self, root, *, fail=False, incomplete=False, wrong_model=False):
        self.root, self.fail, self.incomplete, self.wrong_model = root, fail, incomplete, wrong_model
        self.calls, self.created = [], 0

    def __call__(self, config, credentials_root):
        self.created += 1
        factory = self
        # Constructing a transport is itself after a durable reservation.
        events = sorted((self.root / LEDGER).glob("event-*.json"))
        assert read(events[-1])["kind"] == "call_reserved"

        class Fake:
            def generate(self, system, prompt):
                factory.calls.append((system, json.loads(prompt)))
                if factory.fail:
                    raise RuntimeError("PRIVATE_PROVIDER_ERROR_DO_NOT_STORE")
                response = ScriptedDemoClient().generate(system, prompt)
                response["actual_model"] = "wrong-model" if factory.wrong_model else config.model
                response["usage"] = {"input_tokens": 100, "output_tokens": 200}
                response["usage_complete"] = not factory.incomplete
                return response

            def close(self):
                pass
        return Fake()


def run(setup, factory, model="claude", condition="with_interview", **kwargs):
    root, inputs, config, auth = setup
    return run_live(*inputs, root=root, authorization=auth, config=config, model_name=model,
                    condition=condition, output_dir=root / "runs", client_factory=factory, **kwargs)


def rental(setup, *, started=None, seconds=1800):
    root, _, _, auth = setup
    started = started or datetime.now(timezone.utc) - timedelta(seconds=1)
    value = {"session_id": "rental-test", "started_at": started.isoformat(),
             "deadline": (started + timedelta(seconds=seconds)).isoformat(),
             "session_cap_seconds": seconds, "hourly_usd": 0.6, "status": "running",
             "stopped_verified_at": None, "independent_stop_armed": True}
    save(root / auth["rental_path"], value)
    return value


def test_live_four_arms_share_inputs_and_keep_data_origin_explicit(setup):
    root, _, config, auth = setup
    original_hashes = audit_prior(root)["source_hashes"]
    rental(setup)
    factory = Factory(root)
    results = [run(setup, factory, model, condition) for model in ("claude", "qwen")
               for condition in ("with_interview", "without_interview")]
    assert all(r["status"] == "complete" and r["demo"] is False for r in results)
    assert all(r["synthetic"] is True for r in results)
    assert all(r["model"]["execution_kind"] == "live_provider" for r in results)
    assert all(r["prompt_version"] == "candidate-investigation-v1-live2" for r in results)
    assert len(factory.calls) == 20
    totals = LiveLedger(root, auth, config).status()
    assert totals["stage_calls"] == 20
    assert totals["claude_accounted_usd"] == pytest.approx(0.10114 + 10 * 0.0022)
    assert totals["gpu_seconds"] == pytest.approx(2048.386 + 1800)
    assert audit_prior(root)["source_hashes"] == original_hashes
    for result in results:
        assert verify_run(root / "runs" / result["run_id"])["status"] == "complete"
        assert len(result["budget_receipts"]) == 10
        for stage in result["stages"]:
            payload = json.loads(stage["request"]["prompt"])
            for search in payload.get("previous_searches", []) + payload.get("searches", []):
                assert "results" not in search  # evidence is not duplicated in search history
            if result["condition"] == "without_interview":
                assert "criteria" not in payload
                assert "INTERVIEW_LEAK_SENTINEL" not in stage["request"]["prompt"]


def test_stage_limit_blocks_before_provider_and_never_returns_hold(setup):
    root, _, config, auth = setup
    auth["max_stage_calls"] = 2
    factory = Factory(root)
    result = run(setup, factory)
    assert result["status"] == "budget_blocked" and result["final"] is None
    assert len(factory.calls) == 2
    assert LiveLedger(root, auth, config).status()["stage_calls"] == 2


@pytest.mark.parametrize("failure", ["api", "usage"])
def test_unknown_usage_retains_full_reservations_and_original_ledgers(setup, failure):
    root, _, config, auth = setup
    factory = Factory(root, fail=failure == "api", incomplete=failure == "usage")
    result = run(setup, factory)
    reserves = [r["reserved_claude_usd"] for r in result["budget_receipts"] if r["kind"] == "call_reserved"]
    assert LiveLedger(root, auth, config).status()["claude_accounted_usd"] == pytest.approx(0.10114 + sum(reserves))
    if failure == "api":
        assert result["status"] == "api_error" and result["final"] is None
        assert "PRIVATE_PROVIDER_ERROR_DO_NOT_STORE" not in json.dumps(result)
    assert audit_prior(root)["source_hashes"] == auth["source_hashes"]


def test_existing_task_arm_cannot_repeat_under_new_output_directory(setup):
    root, _, _, _ = setup
    factory = Factory(root)
    run(setup, factory)
    with pytest.raises(BudgetLimitReached, match="already attempted"):
        run(setup, factory)
    assert len(factory.calls) == 5


def test_source_hash_or_input_or_config_change_blocks_before_transport(setup):
    root, inputs, config, auth = setup
    factory = Factory(root)
    inputs[0]["claim"] = "changed claim"
    with pytest.raises(ValueError, match="Inputs or settings"):
        run(setup, factory)
    config["models"]["claude"]["max_tokens"] = 2048
    with pytest.raises(ValueError, match="settings changed"):
        run(setup, factory)
    config["models"]["claude"]["max_tokens"] = 8192
    state = read(root / SOURCES[0]); state["new_field"] = True
    save(root / SOURCES[0], state)
    with pytest.raises(ValueError, match="Historical budget"):
        run(setup, factory)
    assert factory.created == 0


def test_prior_unclosed_claude_reservation_is_carried_forward(setup):
    root, _, _, _ = setup
    state = read(root / SOURCES[0])
    state["attempts"].append({"provider": "claude", "actual_claude_usd": None,
                              "accounted_claude_usd": 0.1, "reserved_claude_usd": 0.3, "status": "inflight"})
    save(root / SOURCES[0], state)
    report = audit_prior(root)
    assert report["claude_accounted_usd"] == pytest.approx(0.40114)
    assert report["unknown_claude_attempts"] == 1


def test_cumulative_claude_cap_blocks_before_transport_creation(setup):
    root, _, _, auth = setup
    state = read(root / SOURCES[0])
    state["attempts"][0].update(actual_claude_usd=1.99999, accounted_claude_usd=1.99999)
    save(root / SOURCES[0], state)
    auth["source_hashes"] = audit_prior(root)["source_hashes"]
    factory = Factory(root)
    result = run(setup, factory)
    assert result["status"] == "budget_blocked" and result["final"] is None
    assert factory.created == 0


def test_total_cap_includes_storage_and_full_gpu_reservation(setup):
    root, _, _, auth = setup
    auth["storage_reserve_usd"] = 4.3
    rental(setup)
    factory = Factory(root)
    with pytest.raises(BudgetLimitReached):
        run(setup, factory)
    assert factory.created == 0


def test_qwen_requires_active_rental_and_full_timeout_margin(setup):
    root, _, _, _ = setup
    factory = Factory(root)
    with pytest.raises(BudgetLimitReached, match="active recorded"):
        run(setup, factory, "qwen")
    rental(setup, started=datetime.now(timezone.utc) - timedelta(seconds=1500))
    with pytest.raises(BudgetLimitReached, match="full request"):
        run(setup, factory, "qwen")
    assert factory.created == 0


def test_gpu_clock_cannot_reset_and_stopped_rental_is_settled_once(setup):
    root, _, config, auth = setup
    original = rental(setup, started=datetime.now(timezone.utc) - timedelta(seconds=60))
    ledger = LiveLedger(root, auth, config)
    assert ledger.status()["gpu_seconds"] == pytest.approx(3848.386)
    changed = deepcopy(original)
    changed["started_at"] = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
    save(root / auth["rental_path"], changed)
    with pytest.raises(ValueError, match="reset"):
        ledger.status()
    original["status"] = "stopped"
    original["stopped_verified_at"] = (datetime.fromisoformat(original["started_at"]) + timedelta(seconds=45)).isoformat()
    save(root / auth["rental_path"], original)
    first = ledger.status()
    assert first["gpu_seconds"] == pytest.approx(2048.386 + 45)
    assert ledger.status() == first


def test_gpu_cumulative_time_cap_not_just_session_cap(setup):
    root, _, config, auth = setup
    cost = read(root / SOURCES[2])
    cost["elapsed_seconds_upper_estimate"] = 6000
    save(root / SOURCES[2], cost)
    auth["source_hashes"] = audit_prior(root)["source_hashes"]
    rental(setup)
    with pytest.raises(BudgetLimitReached):
        LiveLedger(root, auth, config).status()


def test_model_mismatch_is_paid_but_not_a_valid_verdict(setup):
    root, _, config, auth = setup
    result = run(setup, Factory(root, wrong_model=True))
    assert result["status"] == "schema_error" and result["final"] is None
    assert LiveLedger(root, auth, config).status()["stage_calls"] == 1


def test_budget_event_tampering_is_detected(setup):
    root, _, config, auth = setup
    run(setup, Factory(root))
    path = sorted((root / LEDGER).glob("event-*.json"))[1]
    event = read(path); event["reserved_claude_usd"] = 0
    save(path, event)
    with pytest.raises(ValueError, match="integrity"):
        LiveLedger(root, auth, config).status()


def test_authorization_cannot_change_while_adapter_is_alive(setup):
    root, _, config, auth = setup
    ledger = LiveLedger(root, auth, config)
    changed = deepcopy(auth)
    changed["max_stage_calls"] = 19
    save(root / LEDGER / "authorization.json", changed)
    with pytest.raises(ValueError, match="modified"):
        ledger.status()


def test_live_actual_input_origin_stays_non_synthetic(setup):
    root, inputs, _, auth = setup
    inputs[0]["synthetic"] = False
    for doc in inputs[1]:
        doc["synthetic"] = False
    auth["input_hashes"] = {"case": digest(inputs[0]), "corpus": digest(inputs[1]), "criteria": digest(inputs[2])}
    result = run(setup, Factory(root))
    assert result["demo"] is False and result["synthetic"] is False


def supervised_rental(setup):
    value = rental(setup, started=datetime.now(timezone.utc) - timedelta(seconds=400))
    value["independent_stop_armed"] = False
    value["console_stop_supervision"] = {"mode": "active_agent_console", "pod_id": "test-pod",
                                         "deadline": value["deadline"],
                                         "confirmed_at": datetime.now(timezone.utc).isoformat()}
    save(setup[0] / setup[3]["rental_path"], value)
    return value


def test_active_console_supervision_is_explicit_and_recorded_without_claiming_auto_stop(setup):
    root, _, _, _ = setup
    supervised_rental(setup)
    result = run(setup, Factory(root), "qwen")
    assert result["status"] == "complete"
    receipts = [x for x in result["budget_receipts"] if x["kind"] == "call_reserved"]
    assert all(x["gpu_stop_control"]["mode"] == "active_agent_console" for x in receipts)
    assert all(x["gpu_stop_control"]["automatic_stop_verified"] is False for x in receipts)
    assert all(x["gpu_stop_control"]["heartbeat_max_seconds"] == 300 for x in receipts)


@pytest.mark.parametrize("mutation", [
    lambda value: value.pop("console_stop_supervision"),
    lambda value: value["console_stop_supervision"].update(confirmed_at=(datetime.now(timezone.utc) - timedelta(seconds=301)).isoformat()),
    lambda value: value["console_stop_supervision"].update(confirmed_at=(datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()),
    lambda value: value["console_stop_supervision"].update(deadline=(datetime.now(timezone.utc) + timedelta(seconds=2000)).isoformat()),
    lambda value: value["console_stop_supervision"].update(mode="unattended"),
    lambda value: value["console_stop_supervision"].update(api_key="must-not-be-accepted"),
])
def test_missing_stale_or_inconsistent_supervision_blocks_before_provider(setup, mutation):
    root, _, _, auth = setup
    value = supervised_rental(setup)
    mutation(value)
    save(root / auth["rental_path"], value)
    factory = Factory(root)
    with pytest.raises((ValueError, BudgetLimitReached)):
        run(setup, factory, "qwen")
    assert factory.created == 0


def test_stopped_supervised_rental_can_settle_after_heartbeat_expires(setup):
    root, _, config, auth = setup
    value = supervised_rental(setup)
    ledger = LiveLedger(root, auth, config)
    ledger.status()
    value["status"] = "stopped"
    value["stopped_verified_at"] = datetime.now(timezone.utc).isoformat()
    value["console_stop_supervision"]["confirmed_at"] = value["started_at"]
    save(root / auth["rental_path"], value)
    assert ledger.status()["gpu_seconds"] < 2048.386 + 401


def failed_qwen_parent(setup, monkeypatch, *, condition="with_interview", fail=True, change_version=True):
    root = setup[0]
    monkeypatch.setattr("trend_verification_v1.engine.LIVE_PROMPT_VERSION", "candidate-investigation-v1-live1")
    rental(setup)
    parent = run(setup, Factory(root, wrong_model=fail), "qwen", condition)
    if change_version:
        monkeypatch.setattr("trend_verification_v1.engine.LIVE_PROMPT_VERSION", "candidate-investigation-v1-live2")
    return parent, root / "runs" / parent["run_id"]


def test_one_manual_diagnostic_preserves_parent_authorization_and_cumulative_calls(setup, monkeypatch):
    root, _, config, auth = setup
    parent, folder = failed_qwen_parent(setup, monkeypatch)
    original = (folder / "run.json").read_bytes()
    auth_bytes = (root / LEDGER / "authorization.json").read_bytes()
    result = run(setup, Factory(root), "qwen", diagnostic_from=folder)
    assert result["status"] == "complete"
    assert result["prompt_version"] == "candidate-investigation-v1-live2"
    assert (folder / "run.json").read_bytes() == original
    assert (root / LEDGER / "authorization.json").read_bytes() == auth_bytes
    ledger = LiveLedger(root, auth, config)
    assert ledger.status()["stage_calls"] == 6
    permit = [e for e in ledger._events() if e["kind"] == "diagnostic_authorized"]
    assert len(permit) == 1 and permit[0]["parent_run_id"] == parent["run_id"]
    assert permit[0]["parent_record_sha256"] == parent["record_sha256"]
    assert permit[0]["automatic_retries"] == 0 and auth["max_recovery_calls"] == 0
    with pytest.raises(BudgetLimitReached, match="already recorded"):
        run(setup, Factory(root), "qwen", diagnostic_from=folder)


@pytest.mark.parametrize("variant", ["complete", "other_arm", "tampered", "same_prompt", "other_model"])
def test_manual_diagnostic_rejects_ineligible_parent_before_transport(setup, monkeypatch, variant):
    root = setup[0]
    parent, folder = failed_qwen_parent(setup, monkeypatch,
        condition="without_interview" if variant == "other_arm" else "with_interview",
        fail=variant != "complete", change_version=variant != "same_prompt")
    if variant == "tampered":
        altered = deepcopy(parent); altered["error"] = None
        save(folder / "run.json", altered)
    factory = Factory(root)
    with pytest.raises(ValueError):
        run(setup, factory, "claude" if variant == "other_model" else "qwen", diagnostic_from=folder)
    assert factory.created == 0


def test_manual_diagnostic_requires_five_remaining_original_calls(setup, monkeypatch):
    root, _, _, auth = setup
    auth["max_stage_calls"] = 5
    _, folder = failed_qwen_parent(setup, monkeypatch)
    factory = Factory(root)
    with pytest.raises(BudgetLimitReached, match="five remaining"):
        run(setup, factory, "qwen", diagnostic_from=folder)
    assert factory.created == 0


def test_live2_explicit_contract_covers_all_ten_hypotheses_without_control_arm_leak(setup):
    root, inputs, _, auth = setup
    criteria = read(ROOT / "data/interview/candidate-hypotheses-v1.json")
    assert len(criteria) == 10 and all(c["reviewed"] is False for c in criteria)
    new_inputs = (inputs[0], inputs[1], criteria)
    auth["input_hashes"]["criteria"] = digest(criteria)
    updated = (root, new_inputs, setup[2], auth)
    with_result = run(updated, Factory(root))
    without_result = run(updated, Factory(root), condition="without_interview")
    assert with_result["status"] == without_result["status"] == "complete"
    for stage in with_result["stages"]:
        payload = json.loads(stage["request"]["prompt"])
        assert set(payload["output_contract"]["required_fields"]) == set(payload["response_schema"])
        assert "application_status=applied는 금지" in payload["criteria_instruction"]
        if stage["stage"] in ("provisional", "final"):
            assert "change_conditions" in payload["output_contract"]["required_fields"]
            assert "criterion_reviews" in payload["output_contract"]["required_fields"]
            assert payload["output_contract"]["required_criterion_ids"] == [f"H{i}" for i in range(1, 11)]
    for stage in without_result["stages"]:
        payload = json.loads(stage["request"]["prompt"])
        assert "criteria" not in payload and "criteria_instruction" not in payload
        assert "criterion_reviews" not in payload["response_schema"]
        assert "required_criterion_ids" not in payload["output_contract"]
        for c in criteria:
            assert c["hypothesis"] not in stage["request"]["prompt"]
            assert json.dumps(c["id"]) not in stage["request"]["prompt"]
