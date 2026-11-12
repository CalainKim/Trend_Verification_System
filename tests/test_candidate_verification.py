"""Offline boundary tests: no research labels, paid calls, or GPU are used."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from trend_research.providers import ModelConfig
from trend_verification_v1.demo import ScriptedDemoClient, load_example
from trend_verification_v1.engine import LiveExecutionDisabled, inspect_live_config, run_case, verify_run
from trend_verification_v1.inputs import digest, prepare_corpus, search, select_candidates


@pytest.fixture
def inputs():
    return load_example(ROOT)


class RecordingClient(ScriptedDemoClient):
    def __init__(self, stage=None, mutate=None, fail=False):
        self.requests = []
        self.stage, self.mutate, self.fail = stage, mutate, fail

    def generate(self, system, prompt):
        request = json.loads(prompt)
        self.requests.append((system, prompt))
        if request["stage"] == self.stage and self.fail:
            raise RuntimeError("DO_NOT_STORE_PRIVATE_PROVIDER_ERROR")
        response = super().generate(system, prompt)
        if request["stage"] == self.stage and self.mutate:
            result = json.loads(response["text"])
            self.mutate(result)
            response["text"] = json.dumps(result, ensure_ascii=False)
        return response


def run(tmp_path, inputs, **kwargs):
    return run_case(*inputs, output_dir=tmp_path, **kwargs)


def test_complete_workflow_records_substantive_revision_and_independent_critic(tmp_path, inputs):
    client = RecordingClient()
    result = run(tmp_path, inputs, client=client)
    assert result["status"] == "complete" and result["synthetic"] is True
    assert [x["stage"] for x in result["stages"]] == ["provisional", "search_plan_1", "search_plan_2", "critic", "final"]
    assert result["stages"][0]["parsed"]["verdict"] == "CONFIRM"
    assert result["final"]["verdict"] == "REJECT"
    assert result["revisions"][0]["changed"] is True
    assert result["revisions"][0]["reason"]
    assert result["searches"][1]["purpose"] == "counterevidence"
    assert all(len(s["results"]) <= 3 for s in result["searches"])
    assert len(client.requests) == 5
    assert result["prompt_version"] == "candidate-investigation-v1"
    assert verify_run(tmp_path / result["run_id"])["record_sha256"] == result["record_sha256"]


def test_without_interview_omits_content_and_related_fields_from_every_request(tmp_path, inputs):
    inputs[2][0]["hypothesis"] = "PRIVATE_CRITERION_SENTINEL"
    client = RecordingClient()
    result = run(tmp_path, inputs, condition="without_interview", client=client)
    assert result["status"] == "complete"
    for system, prompt in client.requests:
        for forbidden in ("PRIVATE_CRITERION_SENTINEL", "INTERVIEW_LEAK_SENTINEL", "LABEL_LEAK_SENTINEL",
                          '"criteria"', '"criteria_instruction"', '"criterion_reviews"', '"H1"'):
            assert forbidden not in system + prompt
    assert "criterion_reviews" not in result["final"]
    assert "input.criteria.json" not in result["artifacts"]
    assert "criteria" not in result["hashes"]


def test_without_interview_is_independent_of_supplied_criterion_contents(tmp_path, inputs):
    first = run(tmp_path, inputs, condition="without_interview")
    inputs[2][0]["hypothesis"] = "Completely changed hypothesis"
    second = run(tmp_path, inputs, condition="without_interview")
    assert first["hashes"]["all_requests"] == second["hashes"]["all_requests"]


def test_four_slots_keep_observations_workflow_and_settings_equal(tmp_path, inputs):
    results = [run(tmp_path, inputs, model_name=m, condition=c) for m in ("claude", "qwen")
               for c in ("with_interview", "without_interview")]
    for key in ("case", "corpus", "eligible_corpus", "settings", "system_prompt"):
        assert len({r["hashes"][key] for r in results}) == 1
    assert len({tuple(s["stage"] for s in r["stages"]) for r in results}) == 1
    assert all(r["model"]["actual_model"] == "scripted-synthetic-v1" for r in results)


def test_cutoff_scope_origin_and_reposts_are_filtered_before_search(inputs):
    eligible, excluded = prepare_corpus(inputs[0], inputs[1])
    reasons = {x["id"]: x["reason"] for x in excluded}
    assert reasons == {"E-repost": "repost", "E-future": "after_cutoff", "E-interview": "non_observation",
                       "E-label": "non_observation", "E-other": "scope_mismatch", "E-unknown-time": "availability_unverified"}
    assert {x["id"] for x in search(eligible, "가상후디 캠페인 정정")} <= {x["id"] for x in eligible}
    assert next(d for d in eligible if d["id"] == "E-search")["scope_relation"] == "context"


def test_frozen_search_is_top_three_deterministic_and_keeps_new_same_family_observations(inputs):
    for index in range(5):
        extra = deepcopy(inputs[1][2])
        extra.update(id=f"counter-{index}", title=f"가상후디 캠페인 정정 {index}")
        inputs[1].append(extra)
    eligible, _ = prepare_corpus(inputs[0], inputs[1])
    assert sum(d["source_family_id"] == "campaign-origin" for d in eligible) == 6
    first = search(eligible, "가상후디 캠페인 정정")
    assert len(first) == 3
    assert first == search(list(reversed(eligible)), "가상후디 캠페인 정정")


@pytest.mark.parametrize("change", [
    lambda corpus: corpus[0].update(observed_at="2026-11-02T00:00:00+09:00"),
    lambda corpus: corpus[0].update(available_at=None),
    lambda corpus: corpus[0]["observations"][0].update(at="2026-11-02T00:00:00+09:00"),
    lambda corpus: corpus[0]["scope"].update(gender="female"),
    lambda corpus: corpus[0].update(kind="interview_criterion"),
])
def test_invalid_initial_evidence_never_reaches_a_model(tmp_path, inputs, change):
    change(inputs[1])
    client = RecordingClient()
    with pytest.raises(ValueError):
        run(tmp_path, inputs, client=client)
    assert client.requests == []


@pytest.mark.parametrize("change", [
    lambda corpus: corpus[3].update(source_family_id="claimed-independent"),
    lambda corpus: corpus[3].update(repost_of="does-not-exist"),
    lambda corpus: corpus[2].update(repost_of="E-repost"),
])
def test_broken_repost_provenance_is_rejected(inputs, change):
    change(inputs[1])
    with pytest.raises(ValueError):
        prepare_corpus(inputs[0], inputs[1])


def test_repost_cannot_launder_an_interview_into_observations(inputs):
    inputs[1][3].update(repost_of="E-interview", source_family_id="E-interview-producer")
    eligible, excluded = prepare_corpus(inputs[0], inputs[1])
    assert "E-repost" not in {x["id"] for x in eligible}
    assert {x["id"]: x["reason"] for x in excluded}["E-repost"] == "non_observation"


@pytest.mark.parametrize("stage,mutation", [
    ("search_plan_1", lambda d: d.update(request_another_search=False)),
    ("search_plan_2", lambda d: d.update(purpose="support")),
    ("search_plan_2", lambda d: d.update(request_another_search=True)),
    ("search_plan_1", lambda d: d.update(query=["query one", "query two"])),
    ("search_plan_1", lambda d: d.update(extra_query="unbounded query")),
])
def test_search_contract_failure_is_not_a_hold(tmp_path, inputs, stage, mutation):
    client = RecordingClient(stage, mutation)
    result = run(tmp_path, inputs, client=client)
    assert result["status"] == "schema_error" and result["final"] is None
    assert len(result["searches"]) <= 1
    assert len(client.requests) <= 3


def test_one_counter_search_can_stop_without_second_search(tmp_path, inputs):
    client = RecordingClient("search_plan_1", lambda d: d.update(
        query="가상후디 캠페인 정정", purpose="counterevidence", request_another_search=False))
    result = run(tmp_path, inputs, client=client)
    assert result["status"] == "complete"
    assert len(result["searches"]) == 1 and len(result["stages"]) == 4


@pytest.mark.parametrize("stage,evidence_id", [("provisional", "E-counter"), ("final", "E-future"),
                                             ("final", "E-label"), ("final", "invented")])
def test_citations_must_have_been_delivered_to_the_current_stage(tmp_path, inputs, stage, evidence_id):
    client = RecordingClient(stage, lambda d: d["support"][0].update(evidence_ids=[evidence_id]))
    result = run(tmp_path, inputs, client=client)
    assert result["status"] == "schema_error" and result["final"] is None
    assert result["stages"][-1]["raw_response"]["text"]


def test_future_missing_alone_cannot_be_hold(tmp_path, inputs):
    client = RecordingClient("final", lambda d: d.update(verdict="HOLD", unknowns=[
        {"code": "future_unobserved", "detail": "미래 실측이 없다는 이유만 제시"}]))
    result = run(tmp_path, inputs, client=client)
    assert result["status"] == "schema_error" and result["final"] is None


def test_context_evidence_cannot_confirm_the_target(tmp_path, inputs):
    inputs[0]["initial_evidence_ids"] = ["E-search"]
    client = RecordingClient("provisional", lambda d: d.update(verdict="CONFIRM", unknowns=[], support=[
        {"text": "전체 검색 반응을 대상 반응으로 주장", "evidence_ids": ["E-search"]}]))
    assert run(tmp_path, inputs, client=client)["status"] == "schema_error"


def test_unreviewed_criterion_cannot_be_labeled_approved(tmp_path, inputs):
    client = RecordingClient("final", lambda d: d["criterion_reviews"][0].update(application_status="applied"))
    assert run(tmp_path, inputs, client=client)["status"] == "schema_error"
    inputs[2][0]["reviewed"] = True
    with pytest.raises(ValueError):
        run(tmp_path, inputs)


def test_api_error_is_distinct_and_does_not_store_exception_or_hold(tmp_path, inputs):
    result = run(tmp_path, inputs, client=RecordingClient("critic", fail=True))
    assert result["status"] == "api_error" and result["final"] is None
    serialized = (tmp_path / result["run_id"] / "run.json").read_text(encoding="utf-8")
    assert "DO_NOT_STORE_PRIVATE_PROVIDER_ERROR" not in serialized
    assert verify_run(tmp_path / result["run_id"])["status"] == "api_error"


@pytest.mark.parametrize("mutation", [
    lambda response: response.update(text="{not valid JSON}"),
    lambda response: response.update(finish_reason="length"),
    lambda response: response.update(actual_model="different-model"),
    lambda response: response.update(usage={"input_tokens": float("nan")}),
])
def test_transport_and_parse_failures_leave_verifiable_schema_errors(tmp_path, inputs, mutation):
    class MalformedClient(ScriptedDemoClient):
        def generate(self, system, prompt):
            response = super().generate(system, prompt)
            if json.loads(prompt)["stage"] == "critic":
                mutation(response)
            return response

    result = run(tmp_path, inputs, client=MalformedClient())
    assert result["status"] == "schema_error" and result["final"] is None
    assert result["stages"][-1]["stage"] == "critic"
    assert verify_run(tmp_path / result["run_id"])["status"] == "schema_error"


def test_immutable_run_does_not_overwrite_and_detects_modified_artifacts(tmp_path, inputs):
    first = run(tmp_path, inputs)
    path = tmp_path / first["run_id"] / "run.json"
    original = path.read_bytes()
    second = run(tmp_path, inputs)
    assert first["run_id"] != second["run_id"] and path.read_bytes() == original
    frozen = path.parent / "01-provisional.request.json"
    frozen.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="artifact"):
        verify_run(path.parent)


def test_run_record_tampering_is_detected(tmp_path, inputs):
    result = run(tmp_path, inputs)
    folder = tmp_path / result["run_id"]
    result["final"]["verdict"] = "CONFIRM"
    (folder / "run.json").write_text(json.dumps(result), encoding="utf-8")
    with pytest.raises(ValueError, match="integrity"):
        verify_run(folder)


def test_scripted_story_can_keep_decision_when_the_counter_observation_changes(tmp_path, inputs):
    inputs[1][2]["observations"][0]["value"] = 3
    result = run(tmp_path, inputs)
    assert result["status"] == "complete" and result["final"]["verdict"] == "CONFIRM"
    assert result["revisions"][0]["changed"] is False


def test_live_gate_cannot_be_enabled_by_config_flag_or_injected_transport(tmp_path, inputs):
    client = RecordingClient()
    with pytest.raises(LiveExecutionDisabled):
        run(tmp_path, inputs, demo=False, client=client)
    client.offline = False
    with pytest.raises(LiveExecutionDisabled):
        run(tmp_path, inputs, client=client)
    config = json.loads((ROOT / "configs/candidate-verification.example.json").read_text(encoding="utf-8"))
    assert inspect_live_config(config)["budget_action"] == "read_only_reference_not_reset"
    config["live_execution_enabled"] = True
    with pytest.raises(LiveExecutionDisabled):
        inspect_live_config(config)
    assert client.requests == []


def test_real_cases_cannot_be_relabelled_as_scripted_study_results(tmp_path, inputs):
    inputs[0]["synthetic"] = False
    with pytest.raises(ValueError, match="synthetic"):
        run(tmp_path, inputs)


def test_selection_is_ordered_excludes_development_and_never_pads_with_synthetic():
    def row(id, **changes):
        item = {"case_id": id, "candidate_family_id": id, "trigger_at": "2026-10-01T00:00:00+09:00",
                "eligible": True, "development_family": False, "synthetic": False, "source_sha256": "a" * 64}
        return {**item, **changes}
    rows = [row("z"), row("b"), row("a"), row("old", development_family=True),
            row("rugby-style", candidate_family_id="rugby"), row("fake", synthetic=True),
            row("a-new-id", candidate_family_id="a", trigger_at="2026-10-02T00:00:00+09:00")]
    first = select_candidates(rows, ["b"], ["rugby"])
    second = select_candidates(list(reversed(rows)), ["b"], ["rugby"])
    assert first == second
    assert [x["case_id"] for x in first["selected"]] == ["a", "z"]
    assert first["status"] == "insufficient_real_candidates"
