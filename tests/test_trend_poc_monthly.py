"""Monthly retrospective tests use only explicit offline transport fixtures."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trend_poc.monthly import (
    MonthlyService, build_monthly_bundle, monthly_outcome, signal,
    validate_manifest, validate_record,
)
from trend_poc.naver import URLS
from trend_poc.review import MODEL, build_payload, digest


KEYWORDS = ["반팔티", "맨투맨", "카라티"]


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import requests

    def blocked(*args, **kwargs):
        raise AssertionError("Monthly tests must never access a live endpoint")

    monkeypatch.setattr(requests.sessions.Session, "request", blocked)


def manifest():
    return {"year": 2025, "cases": [
        {"keyword": keyword, "definition": keyword + " 명칭의 상의만 포함. 액세서리 제외.",
         "expected_label": "선정 참고용 기대 분류; 모델 입력 금지",
         "references": [{"id": "source-" + str(index), "url": "https://example.test/source/" + str(index),
                         "published_at": "2025-11-01", "title": "후속 관측에 관한 선정 참고 제목",
                         "summary": "게시된 의견이며 수치 측정은 없음", "population": "고객군 불명",
                         "kind": "editorial"}]}
        for index, keyword in enumerate(KEYWORDS)
    ]}


def _rehash(record):
    record["request_sha256"] = digest({"url": record["url"], "payload": record["payload"]})
    record["response_sha256"] = digest(record["response"])
    record["record_sha256"] = digest({key: value for key, value in record.items() if key != "record_sha256"})
    return record


def record(channel="shopping", end="2025-04-30", *, future=60, missing=()):
    payload = {"startDate": "2025-03-01", "endDate": end, "timeUnit": "month", "gender": "m"}
    if channel == "shopping":
        payload.update(category="50000169", ages=["20"], keyword=[{"name": k, "param": [k]} for k in KEYWORDS])
    else:
        payload.update(ages=["3", "4"], keywordGroups=[{"groupName": k, "keywords": [k]} for k in KEYWORDS])
    periods = [f"2025-{month:02}-01" for month in range(3, int(end[5:7]) + 1)]
    results = []
    for keyword in KEYWORDS:
        points = [{"period": period, "ratio": 50 if period == "2025-03-01" else 60 if period == "2025-04-01" else future}
                  for period in periods if period[:7] not in missing]
        results.append({"title": keyword, "keyword" if channel == "shopping" else "keywords": [keyword], "data": points})
    response = {"startDate": payload["startDate"], "endDate": end, "timeUnit": "month", "results": results}
    return _rehash({"id": "fixture-" + channel + "-" + end, "provider": "developers", "channel": channel,
                    "url": URLS["developers"][channel], "payload": payload, "response": response,
                    "status": "complete", "collected_at": "2026-10-06T00:00:00+00:00",
                    "available_at": "2026-10-06T00:00:00+00:00",
                    "missing_dates": {keyword: [period for period in periods if period[:7] in missing] for keyword in KEYWORDS}})


class FakeNaver:
    def __init__(self, future=60, events=None):
        self.future = future
        self.calls = []
        self.events = events if events is not None else []
        self.closed = False

    def fetch(self, channel, keywords, start_date, end_date, archive_dir, *, time_unit="date"):
        assert keywords == KEYWORDS and start_date == "2025-03-01" and time_unit == "month"
        self.calls.append((channel, end_date, time_unit))
        self.events.append(f"naver:{channel}:{end_date}")
        return record(channel, end_date, future=self.future)

    def close(self):
        self.closed = True


class FakeClaude:
    def __init__(self, events=None, fail_at=None):
        self.payloads = []
        self.events = events if events is not None else []
        self.fail_at = fail_at

    def generate(self, payload, checkpoint):
        self.payloads.append(deepcopy(payload))
        bundle = json.loads(payload["messages"][0]["content"])
        self.events.append("claude:" + bundle["candidate"]["keyword"])
        evidence_ids = {item["id"] for item in bundle["evidence"]}
        assert {"shopping_features", "search_request"} <= evidence_ids
        result = {"verdict": "WATCH", "summary": "관측된 관심 증가를 근거로 후속 관찰할 가치가 있습니다.",
                  "support": [{"text": "쇼핑 관심 지수가 증가했습니다.", "evidence_ids": ["shopping_features"]}],
                  "against": [{"text": "검색은 연령 범위가 다른 보조 자료입니다.", "evidence_ids": ["search_request"]}],
                  "unknowns": ["실제 판매량은 확인하지 못했습니다."]}
        failed = len(self.payloads) == self.fail_at
        response = {"text": json.dumps(result, ensure_ascii=False), "actual_model": MODEL,
                    "message_id": f"offline-{len(self.payloads)}", "usage": {"input_tokens": 100, "output_tokens": 80},
                    "stop_reason": "max_tokens" if failed else "end_turn", "usage_complete": not failed}
        checkpoint(deepcopy(response))
        return response


def service_for(tmp_path, *, name="run", sources=None, naver=None):
    path = tmp_path / (name + "-manifest.json")
    if not path.exists() or sources is not None:
        path.write_text(json.dumps(sources if sources is not None else manifest(), ensure_ascii=False), encoding="utf-8")
    return MonthlyService(tmp_path, tmp_path / name, path, provider="developers", naver_client=naver or FakeNaver())


def finish(service, claude=None):
    service.collect()
    assert service.review(client=claude or FakeClaude())["status"] == "complete"
    service.evaluate()
    service.verify_complete()


def initial_bytes(service):
    paths = [service.run_dir / name for name in ("plan.json", "initial-requests.json", "frozen.json", "claude-input-preview.json")]
    paths += [service.case_dir(i) / name for i in range(3) for name in ("bundle.json", "claude-request.json")]
    return {str(path.relative_to(service.run_dir)): path.read_bytes() for path in paths if path.exists()}


@pytest.mark.parametrize("values,status,growth", [
    ({"2025-03": 50, "2025-04": 60}, "WATCH", 20),
    ({"2025-03": 50, "2025-04": 59.999}, "NOT_SUPPORTED", 19.998),
    ({"2025-03": 50, "2025-04": 0}, "NOT_SUPPORTED", -100),
    ({"2025-03": 0, "2025-04": 60}, "HOLD", None),
    ({"2025-03": 50}, "HOLD", None),
    ({"2025-04": 60}, "HOLD", None),
])
def test_signal_boundary_missing_and_zero_baseline(values, status, growth):
    result = signal(values)
    assert result["status"] == status
    assert result["growth_pct"] == (pytest.approx(growth) if growth is not None else None)


def test_collection_cannot_fetch_outcomes_before_all_ai_reviews(tmp_path):
    naver = FakeNaver()
    service = service_for(tmp_path, naver=naver)
    service.collect()
    assert naver.calls == [("shopping", "2025-04-30", "month"), ("search", "2025-04-30", "month")]
    with pytest.raises(ValueError, match="세 AI 판단"):
        service.evaluate()
    assert len(naver.calls) == 2
    assert not (service.run_dir / "followup-requests.json").exists()
    assert not service.load("completion.json")


def test_three_once_only_reviews_and_fresh_service_replay_do_not_call_apis(tmp_path):
    events = []
    naver, claude = FakeNaver(events=events), FakeClaude(events=events)
    service = service_for(tmp_path, naver=naver)
    finish(service, claude)
    assert events == ["naver:shopping:2025-04-30", "naver:search:2025-04-30",
                      *["claude:" + keyword for keyword in KEYWORDS],
                      "naver:shopping:2025-10-31", "naver:search:2025-10-31"]
    snapshot, completion = initial_bytes(service), service.load("completion.json")
    assert len(claude.payloads) == 3 and len(naver.calls) == 4
    assert all(json.loads(p["messages"][0]["content"])["historical_available_at"] is None for p in claude.payloads)

    fresh_naver, fresh_claude = FakeNaver(), FakeClaude()
    restarted = service_for(tmp_path, naver=fresh_naver)
    restarted.collect()
    assert restarted.review(client=fresh_claude) == {"status": "complete", "cases": ["complete"] * 3}
    restarted.evaluate()
    restarted.verify_complete()
    assert fresh_naver.calls == [] and fresh_claude.payloads == []
    assert restarted.load("completion.json") == completion
    assert initial_bytes(restarted) == snapshot


def test_failed_ai_is_not_retried_and_future_queries_remain_blocked(tmp_path):
    naver, claude = FakeNaver(), FakeClaude(fail_at=2)
    service = service_for(tmp_path, naver=naver)
    service.collect()
    assert service.review(client=claude) == {"status": "incomplete", "cases": ["complete", "failed", "complete"]}
    failed_bytes = (service.case_dir(1) / "review.json").read_bytes()
    fresh_claude = FakeClaude()
    assert service_for(tmp_path, naver=naver).review(client=fresh_claude)["status"] == "incomplete"
    assert fresh_claude.payloads == [] and len(claude.payloads) == 3
    with pytest.raises(ValueError, match="세 AI 판단"):
        service.evaluate()
    assert len(naver.calls) == 2
    assert (service.case_dir(1) / "review.json").read_bytes() == failed_bytes


def test_future_values_and_source_expected_labels_cannot_change_april_ai_payload(tmp_path):
    payloads = []
    outcomes = []
    for name, future in (("rising", 80), ("falling", 10)):
        sources = manifest()
        for case in sources["cases"]:
            case["expected_label"] = "FORBIDDEN_EXPECTED_" + name
            case["references"][0]["title"] = "FORBIDDEN_SOURCE_TITLE_" + name
            case["references"][0]["summary"] = "FORBIDDEN_FUTURE_FACT_" + name
        service = service_for(tmp_path, name=name, sources=sources, naver=FakeNaver(future=future))
        claude = FakeClaude()
        service.collect()
        service.review(client=claude)
        before = initial_bytes(service)
        service.evaluate()
        assert initial_bytes(service) == before
        payloads.append(claude.payloads)
        serialized = json.dumps(claude.payloads, ensure_ascii=False)
        assert "FORBIDDEN_" not in serialized
        for payload in claude.payloads:
            context = json.loads(payload["messages"][0]["content"])
            assert "outcome" not in context and "references" not in context
            for evidence in context["evidence"]:
                if "points" in evidence:
                    assert set(evidence["points"]) == {"2025-03", "2025-04"}
        outcomes.append(monthly_outcome(sources["cases"][0], service.load("followup-requests.json"))[1])
    assert payloads[0] == payloads[1]
    assert outcomes[0]["label"] == "후속 관심 상승"
    assert outcomes[1]["label"] == "4월 이후 관심 약화"


def test_future_record_is_rejected_by_initial_bundle_builder():
    records = {channel: record(channel, "2025-10-31") for channel in ("shopping", "search")}
    with pytest.raises(ValueError, match="5월 이후"):
        build_monthly_bundle(manifest()["cases"][0], records)


@pytest.mark.parametrize("mutation", [
    lambda r: r["payload"].update(gender="f"),
    lambda r: r["payload"].update(ages=["30"]),
    lambda r: r["payload"].update(device="pc"),
    lambda r: r["payload"].update(category="different-category"),
    lambda r: r["payload"].update(startDate="2025-02-01"),
    lambda r: r["payload"].update(endDate="2025-05-31"),
    lambda r: r["payload"].update(timeUnit="date"),
    lambda r: r["payload"]["keyword"][0].update(param=[KEYWORDS[0], "다른 표현"]),
    lambda r: r["payload"]["keyword"].append({"name": "새 후보", "param": ["새 후보"]}),
    lambda r: r.update(url="https://example.test/replaced-endpoint"),
])
def test_changed_demographics_window_and_normalization_scope_rejected_even_if_rehashed(mutation):
    raw = record()
    mutation(raw)
    _rehash(raw)
    with pytest.raises(ValueError):
        validate_record(raw, "shopping", KEYWORDS, "2025-04-30")


@pytest.mark.parametrize("field", ["request_sha256", "response_sha256", "record_sha256"])
def test_each_saved_hash_is_checked(field):
    raw = record()
    raw[field] = "incorrect-hash"
    with pytest.raises(ValueError, match="해시"):
        validate_record(raw, "shopping", KEYWORDS, "2025-04-30")


@pytest.mark.parametrize("dates", [
    {"observed_start": "2025-06-01"},
    {"observed_end": "2025-06-30"},
    {"observed_start": "2025-06-30", "observed_end": "2025-06-01"},
    {"observed_start": "2025-06-01", "observed_end": "2025-12-01"},
    {"observed_start": "2025-02-30", "observed_end": "2025-03-01"},
])
def test_source_observation_interval_requires_both_dates_in_order_before_publication(dates):
    sources = manifest()
    sources["cases"][0]["references"][0].update(dates)
    with pytest.raises(ValueError):
        validate_manifest(sources)


@pytest.mark.parametrize("details", [
    {"kind": "measured", "published_at": "2025-08-01"},  # Publication is not an observation interval.
    {"kind": "measured", "published_at": "2025-08-01", "observed_start": "2025-04-01", "observed_end": "2025-04-30"},
    {"kind": "measured", "published_at": "2025-08-01", "observed_start": "2025-04-01", "observed_end": "2025-06-30"},
    {"kind": "editorial", "published_at": "2025-08-01", "observed_start": "2025-06-01", "observed_end": "2025-06-30"},
])
def test_publication_only_april_observations_and_editorials_are_not_future_measured_confirmation(details):
    sources = manifest()
    sources["cases"][0]["references"][0].update(details)
    validate_manifest(sources)
    records = {channel: record(channel, "2025-10-31") for channel in ("shopping", "search")}
    series, outcome = monthly_outcome(sources["cases"][0], records)
    assert outcome["label"] == "확산 여부 미확인"
    assert len(series) == 8
    assert outcome["references"] == sources["cases"][0]["references"]


def test_valid_later_measured_source_is_platform_scoped_confirmation():
    sources = manifest()
    sources["cases"][0]["references"][0].update(
        kind="measured", observed_start="2025-05-01", observed_end="2025-10-31", population="해당 플랫폼 이용자")
    validate_manifest(sources)
    records = {channel: record(channel, "2025-10-31") for channel in ("shopping", "search")}
    outcome = monthly_outcome(sources["cases"][0], records)[1]
    assert outcome["label"] == "플랫폼 반응 확인"
    assert "20대 남성 전체" in outcome["summary"]


@pytest.mark.parametrize("missing,label", [
    (("2025-07",), "일부 기간 미확인"),
    (tuple(f"2025-{month:02}" for month in range(5, 11)), "후속 자료 부족"),
])
def test_missing_outcome_months_remain_unknown_not_failure(missing, label):
    records = {channel: record(channel, "2025-10-31", missing=missing) for channel in ("shopping", "search")}
    series, outcome = monthly_outcome(manifest()["cases"][0], records)
    assert outcome["label"] == label and outcome["missing_months"] == list(missing)
    assert all(row["shopping"] is None and row["search"] is None for row in series if row["month"] in missing)
    assert "실패" not in outcome["label"] and "약화" not in outcome["label"]


@pytest.mark.parametrize("target", ["initial-requests.json", "followup-requests.json", "cases/02/review.json"])
def test_completed_run_blocks_tampered_raw_evidence_and_cached_review(tmp_path, target):
    naver, claude = FakeNaver(), FakeClaude()
    service = service_for(tmp_path, naver=naver)
    finish(service, claude)
    path = service.run_dir / target
    changed = json.loads(path.read_text(encoding="utf-8"))
    if "requests" in target:
        changed["shopping"]["response"]["results"][0]["data"][0]["ratio"] = 49
        _rehash(changed["shopping"])  # Even consistent inner hashes cannot bypass the frozen run hash.
    else:
        changed["result"]["summary"] = "저장 이후 바뀐 AI 판단"
    path.write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError):
        service.verify_complete()
    with pytest.raises(ValueError):
        service.evaluate()
    retry_client = FakeClaude()
    with pytest.raises(ValueError):
        service.review(client=retry_client)
    assert retry_client.payloads == []
    assert len(naver.calls) == 4 and len(claude.payloads) == 3


def test_cli_audit_checks_saved_run_without_constructing_network_clients(tmp_path, monkeypatch, capsys):
    naver = FakeNaver()
    service = service_for(tmp_path, naver=naver)
    finish(service)
    spec = importlib.util.spec_from_file_location("monthly_poc_offline_cli", ROOT / "scripts" / "monthly_poc.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fresh_naver = FakeNaver()
    fresh = service_for(tmp_path, naver=fresh_naver)
    monkeypatch.setattr(module, "MonthlyService", lambda *args, **kwargs: fresh)
    monkeypatch.setattr(sys, "argv", ["monthly_poc.py", "audit", "--run-dir", str(service.run_dir),
                                    "--manifest", str(service.manifest_path), "--provider", "developers"])
    assert module.main() == 0
    assert json.loads(capsys.readouterr().out) == {"status": "verified", "network_calls": 0}
    assert fresh_naver.calls == [] and fresh_naver.closed


def test_explicit_retry_archives_failed_attempt_and_calls_only_selected_case_once(tmp_path):
    naver, claude = FakeNaver(), FakeClaude(fail_at=2)
    service = service_for(tmp_path, naver=naver)
    service.collect()
    assert service.review(client=claude)["cases"] == ["complete", "failed", "complete"]
    case = service.case_dir(1)
    saved_names = ("review.json", "review-partial.json", "claude-request.json")
    originals = {name: json.loads((case / name).read_text(encoding="utf-8")) for name in saved_names}
    old_review_bytes = (case / "review.json").read_bytes()
    # Preserve a recoverable checkpoint left by the previous failed write, too.
    temporary_checkpoint = {"text": "older checkpoint", "usage": {"output_tokens": 9}}
    (case / "review-partial.json.tmp").write_text(json.dumps(temporary_checkpoint), encoding="utf-8")
    other_cases = {i: (service.case_dir(i) / "review.json").read_bytes() for i in (0, 2)}

    no_retry = FakeClaude()
    assert service.review(client=no_retry)["status"] == "incomplete"
    assert no_retry.payloads == [] and len(claude.payloads) == 3
    assert not (case / "attempts").exists()

    retried = service.retry_review(1, client=claude)
    assert retried["status"] == "complete" and len(claude.payloads) == 4
    assert json.loads(claude.payloads[-1]["messages"][0]["content"])["candidate"]["keyword"] == KEYWORDS[1]
    assert claude.payloads[-1] == claude.payloads[1]
    archives = list((case / "attempts").iterdir())
    assert len(archives) == 1
    archive = archives[0]
    for name, expected in originals.items():
        assert json.loads((archive / name).read_text(encoding="utf-8")) == expected
    assert (archive / "review.json").read_bytes() == old_review_bytes
    assert json.loads((archive / "review-partial.json.tmp").read_text(encoding="utf-8")) == temporary_checkpoint
    retry_record = json.loads((archive / "retry.json").read_text(encoding="utf-8"))
    assert retry_record["previous_input_sha256"] == originals["review.json"]["input_sha256"] == retried["input_sha256"]
    assert {i: (service.case_dir(i) / "review.json").read_bytes() for i in (0, 2)} == other_cases

    fresh_claude = FakeClaude()
    assert service_for(tmp_path, naver=naver).review(client=fresh_claude)["status"] == "complete"
    assert fresh_claude.payloads == []
    with pytest.raises(ValueError, match="실패 상태"):
        service.retry_review(1, client=fresh_claude)
    assert len(list((case / "attempts").iterdir())) == 1
    assert fresh_claude.payloads == [] and len(naver.calls) == 2
    service.evaluate()
    service.verify_complete()


def test_explicit_retry_that_fails_still_does_not_auto_retry(tmp_path):
    service = service_for(tmp_path)
    service.collect()
    assert service.review(client=FakeClaude(fail_at=1))["status"] == "incomplete"
    failed_retry = FakeClaude(fail_at=1)
    assert service.retry_review(0, client=failed_retry)["status"] == "failed"
    assert len(failed_retry.payloads) == 1
    archive = next((service.case_dir(0) / "attempts").iterdir())
    assert json.loads((archive / "review.json").read_text(encoding="utf-8"))["status"] == "failed"
    no_retry = FakeClaude()
    assert service.review(client=no_retry)["status"] == "incomplete"
    with pytest.raises(ValueError, match="세 AI 판단"):
        service.evaluate()
    assert no_retry.payloads == [] and len(service.naver.calls) == 2


@pytest.mark.parametrize("state", ["not_run", "running", "complete", "completed_run"])
def test_explicit_retry_rejects_non_failed_or_completed_runs_before_api_call(tmp_path, state):
    naver = FakeNaver()
    service = service_for(tmp_path, naver=naver)
    service.collect()
    if state in ("complete", "completed_run"):
        service.review(client=FakeClaude())
        if state == "completed_run":
            service.evaluate()
    elif state == "running":
        path = service.case_dir(0) / "review.json"
        bundle = json.loads((service.case_dir(0) / "bundle.json").read_text(encoding="utf-8"))
        path.write_text(json.dumps({"status": "running", "input_sha256": digest(build_payload(bundle))}), encoding="utf-8")
    before = len(naver.calls)
    retry_client = FakeClaude()
    with pytest.raises(ValueError):
        service.retry_review(0, client=retry_client)
    assert retry_client.payloads == [] and len(naver.calls) == before
    assert not (service.case_dir(0) / "attempts").exists()


@pytest.mark.parametrize("index", [-1, 3])
def test_explicit_retry_rejects_out_of_range_case_without_api_calls(tmp_path, index):
    service = service_for(tmp_path)
    service.collect()
    service.review(client=FakeClaude(fail_at=1))
    retry_client = FakeClaude()
    with pytest.raises(ValueError):
        service.retry_review(index, client=retry_client)
    assert retry_client.payloads == []


def test_initial_and_followup_indices_are_compared_only_within_their_own_normalization_window():
    case = manifest()["cases"][0]
    initial = {channel: record(channel) for channel in ("shopping", "search")}
    bundle = build_monthly_bundle(case, initial)
    later = {channel: record(channel, "2025-10-31", future=80) for channel in ("shopping", "search")}
    for channel, raw in later.items():
        for series in raw["response"]["results"]:
            for point in series["data"]:
                point["ratio"] /= 2
        _rehash(raw)
        validate_record(raw, channel, KEYWORDS, "2025-10-31")
    values, outcome = monthly_outcome(case, later)
    assert bundle["features"]["shopping"] == {"status": "WATCH", "march": 50, "april": 60, "growth_pct": 20}
    assert next(row for row in values if row["month"] == "2025-04")["shopping"] == 30
    # May's 40 is higher than April's 30 in this request. Comparing it to the
    # initial request's 60 would falsely label the same pattern as weakening.
    assert next(row for row in values if row["month"] == "2025-05")["shopping"] == 40
    assert outcome["label"] == "후속 관심 상승"
