import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from trend_poc.review import MODEL, build_payload, run_review, validate_result
import pytest


BUNDLE = {"candidate": "반팔티", "simulated_cutoff": "2025-04-08", "evidence": [{"id": "shopping_features", "data": {"growth_pct": 25}}]}
RESULT = {"verdict": "WATCH", "summary": "후속 관찰 가치가 있습니다.",
          "support": [{"text": "기준 대비 관심 증가", "evidence_ids": ["shopping_features"]}],
          "against": [], "unknowns": ["판매량 미확인"]}


def response(result=None):
    return {"text": json.dumps(result or RESULT, ensure_ascii=False), "stop_reason": "end_turn", "usage_complete": True,
            "actual_model": MODEL, "message_id": "mock-test-only", "usage": {"input_tokens": 10, "output_tokens": 10}}


class FakeClient:
    def __init__(self, fail=False):
        self.calls = 0
        self.fail = fail

    def generate(self, payload, checkpoint):
        self.calls += 1
        if self.fail:
            raise RuntimeError("sensitive message must not be saved")
        return response()


def test_future_outcome_not_in_api_payload():
    bundle = dict(BUNDLE, outcome={"october_answer": "secret future label"}, human_decision="future-informed")
    serialized = json.dumps(build_payload(bundle))
    assert "october_answer" not in serialized and "future-informed" not in serialized


def test_invalid_citation_and_truncated_response():
    wrong = copy.deepcopy(RESULT)
    wrong["support"][0]["evidence_ids"] = ["nonexistent"]
    with pytest.raises(ValueError):
        validate_result(response(wrong), BUNDLE)
    clipped = response()
    clipped["stop_reason"] = "max_tokens"
    with pytest.raises(ValueError):
        validate_result(clipped, BUNDLE)


def test_repeated_execution_reuses_one_paid_call(tmp_path):
    client = FakeClient()
    first = run_review(tmp_path, tmp_path, BUNDLE, client)
    assert first["status"] == "complete"
    assert run_review(tmp_path, tmp_path, BUNDLE, client) == first
    assert client.calls == 1
    with pytest.raises(ValueError):
        run_review(tmp_path, tmp_path, dict(BUNDLE, candidate="different"), client)


def test_failure_is_not_retried_and_secrets_are_not_logged(tmp_path):
    client = FakeClient(fail=True)
    assert run_review(tmp_path, tmp_path, BUNDLE, client)["status"] == "failed"
    run_review(tmp_path, tmp_path, BUNDLE, client)
    assert client.calls == 1
    assert "sensitive" not in (tmp_path / "review.json").read_text(encoding="utf-8")


def test_checkpoint_file_lock_does_not_abort_or_repeat_paid_stream(tmp_path, monkeypatch):
    import trend_poc.review as module
    original = module.save
    def locked_checkpoint(path, value):
        if Path(path).name == "review-partial.json":
            raise PermissionError("temporary local file lock")
        return original(path, value)
    monkeypatch.setattr(module, "save", locked_checkpoint)
    class StreamingFake(FakeClient):
        def generate(self, payload, checkpoint):
            self.calls += 1
            checkpoint({"text": "partial", "stop_reason": None})
            checkpoint(dict(response(), stop_reason="end_turn"))
            return response()
    client = StreamingFake()
    record = run_review(tmp_path, tmp_path, BUNDLE, client)
    assert record["status"] == "complete"
    assert record["checkpoint_write_errors"] == 2
    assert run_review(tmp_path, tmp_path, BUNDLE, client) == record
    assert client.calls == 1
