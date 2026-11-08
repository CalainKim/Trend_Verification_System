"""Hand-computed scoring and final-answer validation, without benchmark labels."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trend_research.evaluation import evaluate, validate_result


@pytest.fixture
def prepared():
    return {"case_id": "fictional", "evidence": [
        {"id": "rank_history", "observation": "2026-10-01: 80위, 2026-10-02: 40위"},
        {"id": "rank_features", "observation": "기준 평균 80.00, 감지 평균 40.00, 상승폭 40.00"},
    ]}


def answer(verdict="WATCH"):
    return {"verdict": verdict, "summary": "상승이 이어질 가능성을 관찰한다.",
            "support": [{"text": "순위가 80위에서 40위로 올랐다.", "evidence_ids": ["rank_history"]}],
            "against": [], "unknowns": ["향후 순위는 관측하지 못했다."]}


@pytest.mark.parametrize("finish", ["stop", "end_turn"])
def test_both_provider_finish_codes_and_fenced_json(prepared, finish):
    result = validate_result("```json\n" + json.dumps(answer(), ensure_ascii=False) + "\n```", prepared, finish)
    assert result["status"] == "complete"
    assert result["result"]["verdict"] == "WATCH"
    assert result["numeric_flags"] == []


@pytest.mark.parametrize("finish", ["length", "max_tokens", "incomplete_thinking", "tool_use", None])
def test_truncation_never_becomes_hold(prepared, finish):
    result = validate_result(json.dumps(answer("HOLD")), prepared, finish)
    assert result["status"] == "invalid"
    assert result["result"] is None
    assert "response_not_complete" in result["errors"]


def test_unknown_reference_and_missing_citation_rejected(prepared):
    value = answer()
    value["support"][0]["evidence_ids"] = ["future_sales"]
    result = validate_result(json.dumps(value), prepared, "stop")
    assert "support[0]:unknown_evidence_id" in result["errors"]
    value["support"][0]["evidence_ids"] = []
    assert validate_result(json.dumps(value), prepared, "stop")["status"] == "invalid"


@pytest.mark.parametrize("text", [
    '{"verdict":"HOLD","verdict":"WATCH"}',
    '{"verdict":NaN}',
    'Here is the answer: {"verdict":"HOLD"}',
    '[]', '',
])
def test_invalid_json_shapes_and_duplicate_keys(prepared, text):
    assert validate_result(text, prepared, "stop")["status"] == "invalid"


def test_structural_contract_and_numeric_flags_are_distinct(prepared):
    value = answer()
    value["support"][0]["text"] = "판매량이 999개 증가했다."
    result = validate_result(json.dumps(value), prepared, "stop")
    assert result["status"] == "complete"  # Semantic support is not certified by the parser.
    assert result["numeric_flags"][0]["number"] == "999"
    assert result["warnings"]
    value["support"][0]["text"] = "40.0위만큼 올랐다."
    assert validate_result(json.dumps(value), prepared, "stop")["numeric_flags"] == []
    value["unexpected"] = "ignored?"
    assert validate_result(json.dumps(value), prepared, "stop")["status"] == "invalid"


@pytest.mark.parametrize("verdict", [[], {}, None, 1, True])
def test_invalid_verdict_types_do_not_crash_validation(prepared, verdict):
    value = answer()
    value["verdict"] = verdict
    result = validate_result(json.dumps(value), prepared, "stop")
    assert result["status"] == "invalid"
    assert "invalid_verdict" in result["errors"]


def test_numeric_checks_use_cited_sources_not_other_evidence(prepared):
    prepared["evidence"].append({"id": "other", "observation": "상승폭 99"})
    value = answer()
    value["support"][0]["text"] = "99위만큼 올랐다."
    result = validate_result(json.dumps(value), prepared, "stop")
    assert result["numeric_flags"] == [{"field": "support[0]", "number": "99",
        "evidence_ids": ["rank_history"], "kind": "number_not_literal_in_cited_evidence"}]


def record(cid, verdict=None, status="complete", **extras):
    return {"case_id": cid, "status": status,
            "result": {"verdict": verdict} if verdict is not None else None, **extras}


def test_exact_partition_recall_includes_hold_and_failure():
    labels = {"a": "persist", "b": "persist", "c": "persist", "d": "persist",
              "e": "fade", "f": "fade", "g": "fade", "h": "fade"}
    records = [record("a", "WATCH", elapsed_seconds=2, cost_usd=.02,
                      usage={"input_tokens": 10, "output_tokens": 20}),
               record("b", "NOT_SUPPORTED"), record("c", "HOLD"),
               record("d", status="failed"), record("e", "WATCH"),
               record("f", "NOT_SUPPORTED"), record("g", "HOLD")]
    card = evaluate(records, labels, list(labels))
    assert card["n_cases"] == 8
    assert (card["n_answered"], card["n_hold"], card["n_failed"], card["n_missing"]) == (4, 2, 2, 1)
    assert card["correct"] == card["wrong"] == 2
    assert card["coverage"] == card["answered_accuracy"] == .5
    assert card["persist_precision"] == .5
    assert card["persist_recall"] == .25
    assert card["persist_f1"] == pytest.approx(1/3)
    assert sum(card[k] for k in ("correct_rate", "wrong_rate", "hold_rate", "failure_rate")) == 1
    assert card["confusion"] == {
        "persist": {"WATCH": 1, "NOT_SUPPORTED": 1, "HOLD": 1},
        "fade": {"WATCH": 1, "NOT_SUPPORTED": 1, "HOLD": 1}}
    assert card["failures_by_truth"] == {"persist": 1, "fade": 1}
    assert card["cost_record_count"] == 1
    assert card["cost_total_usd"] == .02
    assert card["usage"]["reasoning_tokens"] is None


@pytest.mark.parametrize("status", ["failed", "invalid", "budget_skipped", "interrupted"])
def test_failed_record_cannot_smuggle_a_valid_verdict(status):
    card = evaluate([record("a", "WATCH", status=status)], {"a": "persist"}, ["a"])
    assert card["n_failed"] == 1
    assert card["n_hold"] == card["correct"] == 0
    assert card["persist_recall"] == 0
    assert card["persist_precision"] is None


def test_complete_missing_verdict_is_invalid_not_hold():
    card = evaluate([record("a")], {"a": "fade"}, ["a"])
    assert card["status_counts"]["invalid"] == 1
    assert card["n_hold"] == 0


def test_all_hold_and_zero_denominators():
    card = evaluate([record("a", "HOLD")], {"a": "persist"}, ["a"])
    assert card["n_hold"] == 1
    assert card["n_failed"] == 0
    assert card["answered_accuracy"] is None
    assert card["answered_accuracy_ci95"] is None
    assert card["persist_recall"] == 0
    empty = evaluate([], {}, [])
    for key in ("coverage", "answered_accuracy", "persist_precision", "persist_recall", "cost_total_usd"):
        assert empty[key] is None


def test_labels_and_case_integrity():
    with pytest.raises(ValueError, match="duplicate_record"):
        evaluate([record("a", "WATCH"), record("a", "WATCH")], {"a": "persist"}, ["a"])
    with pytest.raises(ValueError, match="unexpected_record"):
        evaluate([record("b", "WATCH")], {"a": "persist"}, ["a"])
    with pytest.raises(ValueError, match="missing_truth"):
        evaluate([], {}, ["a"])
    with pytest.raises(ValueError, match="unsupported_truth"):
        evaluate([], {"a": "WATCH"}, ["a"])
    with pytest.raises(ValueError, match="unique_strings"):
        evaluate([], {"a": "persist"}, ["a", "a"])
    # A sealed full benchmark may contain truth outside the selected cohort.
    card = evaluate([record("a", "WATCH")], {"a": "persist", "other": "fade"}, ["a"])
    assert card["n_cases"] == 1


def test_costs_and_timing_include_failed_attempt_records_but_missing_is_not_zero():
    card = evaluate([record("a", status="failed", elapsed_seconds=4, estimated_cost_usd=.1),
                     record("b", "HOLD", elapsed_seconds=2)],
                    {"a": "fade", "b": "persist"}, ["a", "b"])
    assert card["elapsed_seconds_mean"] == card["elapsed_seconds_median"] == 3
    assert card["cost_total_usd"] is None
    assert card["cost_record_count"] == 0
    assert card["actual_cost_complete"] is False
    assert card["accounted_cost_known_subtotal_usd"] == .1
    assert card["accounted_cost_total_usd"] is None
    assert card["accounted_cost_record_count"] == card["reserved_cost_record_count"] == 1
    assert card["accounted_cost_missing_count"] == 1
    assert evaluate([record("a", "HOLD")], {"a": "fade"}, ["a"])["cost_total_usd"] is None


def test_unknown_retry_charge_stays_reserved_not_actual_after_success():
    card = evaluate([
        record("a", "WATCH", cost_usd=.02, estimated_cost_usd=.2),
        record("b", "HOLD", cost_usd=None, estimated_cost_usd=.15),
    ], {"a": "persist", "b": "fade"}, ["a", "b"])
    assert card["actual_cost_total_usd"] is None
    assert card["actual_cost_known_subtotal_usd"] == .02
    assert card["actual_cost_record_count"] == card["actual_cost_missing_count"] == 1
    assert card["actual_cost_complete"] is False
    assert card["accounted_cost_total_usd"] == pytest.approx(.17)
    assert card["accounted_cost_record_count"] == 2
    assert card["accounted_cost_complete"] is True
    assert card["reserved_cost_record_count"] == 1


def test_cost_completeness_requires_all_expected_cases_and_accepts_explicit_zero():
    full = evaluate([record("a", "HOLD", cost_usd=0)], {"a": "fade"}, ["a"])
    assert full["actual_cost_total_usd"] == 0
    assert full["actual_cost_complete"] is True
    assert full["accounted_cost_complete"] is True
    partial = evaluate([record("a", "HOLD", cost_usd=.1)],
                       {"a": "fade", "b": "persist"}, ["a", "b"])
    assert partial["actual_cost_known_subtotal_usd"] == .1
    assert partial["actual_cost_total_usd"] is None
    assert partial["accounted_cost_total_usd"] is None
    assert partial["actual_cost_missing_count"] == 1


def test_tokens_with_unknown_prior_attempt_are_only_known_subtotals():
    card = evaluate([record("a", "HOLD", usage={"input_tokens": 10, "output_tokens": 20},
                            usage_complete=False)], {"a": "fade"}, ["a"])
    assert card["usage"] == {"input_tokens": 10, "output_tokens": 20, "reasoning_tokens": None}
    assert card["usage_complete"] is False
    assert card["usage_complete_record_count"] == 0
    full = evaluate([record("a", "HOLD", usage={"input_tokens": 10, "output_tokens": 20},
                            usage_complete=True)], {"a": "fade"}, ["a"])
    assert full["usage_complete"] is True


@pytest.mark.parametrize("cost", [float("nan"), float("inf"), -1, True, "0.1"])
def test_invalid_actual_cost_does_not_hide_valid_reservation(cost):
    card = evaluate([record("a", "HOLD", cost_usd=cost, estimated_cost_usd=.1)],
                    {"a": "fade"}, ["a"])
    assert card["actual_cost_total_usd"] is None
    assert card["accounted_cost_total_usd"] == .1
