"""Ablation isolation, source integrity, and rank-boundary regression cases."""
from copy import deepcopy
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trend_research.inputs import (
    PILOT_IDS, FORECAST_SYSTEM_PROMPT, baseline_predictions, build_prompt, load_cases, load_manifest,
    parse_rank_history, prepare_case,
)


ROOT = Path(__file__).resolve().parents[1]


def test_prompt_versions_preserve_frozen_v1_and_identical_eight_observation_inputs():
    reference = json.loads((ROOT / "docs/research/pilot-prompt-v1.json").read_text(encoding="utf-8"))
    manifest = load_manifest(repo_root=ROOT)
    cases = load_cases(manifest, ROOT)
    for case in cases:
        prepared = prepare_case(case, "structured")
        original = deepcopy(prepared)
        old_system, old_user = build_prompt(prepared)
        explicit_old = build_prompt(prepared, "pilot-v1")
        new_system, new_user = build_prompt(prepared, "forecast-v2")
        assert (old_system, old_user) == explicit_old
        assert old_system == reference["system"]
        assert new_system == FORECAST_SYSTEM_PROMPT != old_system
        assert old_user == new_user
        assert json.loads(new_user) == original == prepared
        if case["case_id"] == reference["case_id"]:
            assert old_user == reference["user"]


def test_unknown_prompt_version_is_rejected():
    with pytest.raises(ValueError, match="prompt version"):
        build_prompt(prepare_case(source_case(), "structured"), "forecast-typo")


def source_case(ranks=None, start=date(2026, 9, 29)):
    ranks = ranks if ranks is not None else [80] * 7 + [30, 30, 30, 40, 40, 50, 60]
    days = [start + timedelta(days=i) for i in range(14)]
    pairs = ", ".join(
        f"{d:%m-%d} {'TOP100 밖' if r is None else str(r) + '위'}"
        for d, r in zip(days, ranks)
    )
    return {
        "case_id": "fixture-sweatshirt",
        "experiment_type": "persistence-v1",
        "horizon_days": 7,
        "simulated_cutoff": days[-1].isoformat(),
        "t_cut": days[-1].isoformat(),
        "item": {"key": "29cm:fixture", "name": "fixture sweatshirt", "brand": "fixture"},
        "candidate": {"keyword": "DO_NOT_FORWARD", "definition": "DO_NOT_FORWARD"},
        "claim": "DO_NOT_FORWARD",
        "features": {"rank_base": -99999, "rank_rise": 99999, "review_delta": 88888},
        "evidence": [
            {"id": "rank_change", "observation": (
                f"순위 평균이 {days[0]}~{days[6]} 구간 999위에서 "
                f"{days[7]}~{days[13]} 구간 888위로 111계단 올랐다"
            )},
            {"id": "rank_daily", "observation": f"일별 순위는 {pairs} 다. DO_NOT_FORWARD 변화량 55555 계절성 77777"},
            {"id": "seasonality", "observation": "DO_NOT_FORWARD 77777"},
            {"id": "review_change", "observation": "DO_NOT_FORWARD 88888"},
        ],
        "limitations": ["DO_NOT_FORWARD 44444"],
        "label": "DO_NOT_FORWARD_LABEL",
        "future": [{"date": "2027-01-01", "rank": 1}],
    }


def test_frozen_eight_cases_are_integrity_checked_without_labels():
    manifest = load_manifest(repo_root=ROOT)
    cases = load_cases(manifest, ROOT)
    assert [x["case_id"] for x in cases] == list(PILOT_IDS)
    assert len({x["product_group_id"] for x in manifest["cases"]}) == 7
    for case in cases:
        history = parse_rank_history(case)
        assert len(history) == 14
        assert history[-1]["date"] == "2026-10-12"
        assert set(baseline_predictions(case)) == {
            "always_persist", "always_fade", "last_rank", "last3_mean",
        }


@pytest.mark.parametrize("view", ["static", "history", "structured"])
def test_source_prose_and_nonrank_features_never_leak_into_views(view):
    original = source_case()
    snapshot = deepcopy(original)
    prepared = prepare_case(original, view)
    system, user = build_prompt(prepared)
    for marker in ("DO_NOT_FORWARD", "99999", "88888", "77777", "55555", "44444", "2027-01-01"):
        assert marker not in user
    assert original == snapshot
    assert "7개 관측일" in prepared["claim"]
    assert "7일 동안" not in prepared["claim"]
    assert json.loads(user) == prepared
    assert "WATCH" in system


def test_views_isolate_current_state_history_and_computed_features():
    case = source_case()
    static = prepare_case(case, "static")
    history = prepare_case(case, "history")
    structured = prepare_case(case, "structured")
    assert "history" not in static and "features" not in static
    assert len(static["evidence"]) == 1
    assert "2026-09-29" not in build_prompt(static)[1]
    assert "80위" not in build_prompt(static)[1]
    assert "features" not in history
    assert [x["id"] for x in history["evidence"]] == ["current_rank", "rank_history"]
    assert history["history"] == structured["history"]
    assert history["evidence"] == structured["evidence"][:2]
    # These expected figures are independently hand-calculated from the fixture.
    assert structured["features"]["base_mean_rank"] == 80
    assert structured["features"]["detect_mean_rank"] == 40
    assert structured["features"]["rank_improvement"] == 40
    assert structured["features"]["confirmation_mean_rank_threshold"] == 60


def test_baselines_use_raw_means_and_include_exact_retention_boundary():
    case = source_case()
    assert baseline_predictions(case) == {
        "always_persist": "WATCH", "always_fade": "NOT_SUPPORTED",
        "last_rank": "WATCH", "last3_mean": "WATCH",
    }
    # The detect mean remains 40, but the last point crosses the 60 boundary.
    case = source_case([80] * 7 + [29, 30, 30, 40, 40, 50, 61])
    assert baseline_predictions(case)["last_rank"] == "NOT_SUPPORTED"
    assert baseline_predictions(case)["last3_mean"] == "WATCH"


def test_unlisted_is_boundary_not_observed_rank_and_still_counts_in_mean():
    case = source_case([None] * 7 + [20, 20, 20, 20, 20, 20, None])
    history = parse_rank_history(case)
    assert history[0] == {
        "date": "2026-09-29", "rank": None,
        "rank_for_calculation": 101, "status": "not_in_collected_top100",
    }
    features = prepare_case(case, "structured")["features"]
    assert features["base_mean_rank"] == 101
    assert features["detect_mean_rank"] == 31.57  # (6*20 + 101) / 7
    assert features["base_in_list_fraction"] == 0
    assert features["detect_in_list_fraction"] == 0.8571
    assert baseline_predictions(case)["last_rank"] == "NOT_SUPPORTED"
    assert "실제 순위는 알 수 없다" in prepare_case(case, "static")["evidence"][0]["observation"]


def test_year_boundary_is_anchored_by_full_source_dates():
    case = source_case(start=date(2025, 12, 25))
    history = parse_rank_history(case)
    assert history[0]["date"] == "2025-12-25"
    assert history[-1]["date"] == "2026-01-07"


@pytest.mark.parametrize("mutation", ["duplicate", "thirteen", "future", "bad_rank", "wrong_anchor", "duplicate_evidence"])
def test_ambiguous_or_malformed_history_is_rejected(mutation):
    case = source_case()
    observation = case["evidence"][1]["observation"]
    if mutation == "duplicate":
        observation = observation.replace("09-30 80위", "09-29 80위")
    elif mutation == "thirteen":
        observation = observation.replace("09-29 80위, ", "")
    elif mutation == "future":
        observation = observation.replace("09-29 80위", "10-13 80위")
    elif mutation == "bad_rank":
        observation = observation.replace("09-29 80위", "09-29 101위")
    elif mutation == "wrong_anchor":
        case["evidence"][0]["observation"] = case["evidence"][0]["observation"].replace("2026-09-29", "2026-09-28")
    else:
        case["evidence"].append(deepcopy(case["evidence"][1]))
    case["evidence"][1]["observation"] = observation
    with pytest.raises(ValueError):
        parse_rank_history(case)


def test_manifest_rejects_changed_selection_and_source_content(tmp_path):
    manifest = load_manifest(repo_root=ROOT)
    bad_selection = deepcopy(manifest)
    bad_selection["cases"].reverse()
    with pytest.raises(ValueError, match="selection"):
        load_cases(bad_selection, ROOT)
    tampered = deepcopy(manifest)
    tampered["cases"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="hash mismatch"):
        load_cases(tampered, ROOT)


def test_checkout_line_endings_do_not_change_frozen_source_hashes(tmp_path):
    manifest = load_manifest(repo_root=ROOT)
    for entry in manifest["cases"]:
        source = (ROOT / entry["path"]).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(source).hexdigest() == entry["sha256"]
        target = tmp_path / entry["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.replace(b"\n", b"\r\n"))
    assert len(load_cases(manifest, tmp_path)) == 8


def test_unsupported_view_and_different_horizon_are_rejected():
    with pytest.raises(ValueError, match="view"):
        prepare_case(source_case(), "all")
    case = source_case()
    case["horizon_days"] = 28
    with pytest.raises(ValueError, match="horizon"):
        prepare_case(case, "structured")
