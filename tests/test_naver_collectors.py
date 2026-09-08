"""네이버 수집기 검증. 실제 호출 없이 응답 형태만 흉내낸다.

키가 나오기 전에도 파싱·저장 규약이 맞는지 확인해두기 위한 것이다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trend_pipeline import storage  # noqa: E402
from trend_pipeline.collectors.naver_base import NaverApiError  # noqa: E402
from trend_pipeline.collectors.naver_datalab import NaverDataLabCollector  # noqa: E402
from trend_pipeline.collectors.naver_shopping import NaverShoppingCollector  # noqa: E402


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status
        self.text = json.dumps(payload, ensure_ascii=False)

    def json(self):
        return self._payload


class FakeSession:
    """보낸 요청을 기록하고 미리 정한 응답을 돌려준다."""

    def __init__(self, payloads):
        self.headers = {}
        self._payloads = list(payloads)
        self.calls = []

    def post(self, url, data=None, timeout=None):
        self.calls.append((url, json.loads(data.decode("utf-8"))))
        item = self._payloads.pop(0)
        return FakeResponse(item, status=item.pop("__status", 200)) if isinstance(item, dict) else item


SEARCH_RESPONSE = {
    "startDate": "2024-10-01", "endDate": "2024-10-03", "timeUnit": "date",
    "results": [{
        "title": "발라클라바", "keywords": ["발라클라바", "바라클라바"],
        "data": [{"period": "2024-10-01", "ratio": 12.5},
                 {"period": "2024-10-02", "ratio": 48.0},
                 {"period": "2024-10-03", "ratio": 100.0}],
    }],
}


def test_search_trend_parsed_into_records():
    s = FakeSession([SEARCH_RESPONSE])
    c = NaverDataLabCollector("id", "secret", min_interval_sec=0, session=s)
    rows = list(c.collect({"발라클라바": ["발라클라바", "바라클라바"]},
                          "2024-10-01", "2024-10-03"))
    assert len(rows) == 3
    assert [r.observed_at for r in rows] == ["2024-10-01", "2024-10-02", "2024-10-03"]
    assert [r.metric_value for r in rows] == [12.5, 48.0, 100.0]
    assert all(r.channel == "naver_datalab" and r.metric_type == "search_index" for r in rows)
    # 동의어 묶음이 메타데이터에 남아야 나중에 무엇이 합산됐는지 추적된다
    assert rows[0].metadata["keywords"] == ["발라클라바", "바라클라바"]
    assert rows[0].metadata["normalized"] is True


def test_search_trend_sends_expected_request():
    s = FakeSession([SEARCH_RESPONSE])
    c = NaverDataLabCollector("id", "secret", min_interval_sec=0, session=s)
    list(c.collect({"발라클라바": ["발라클라바"]}, "2024-10-01", "2024-10-03",
                   gender="f", ages=["4", "5"]))
    url, body = s.calls[0]
    assert url.endswith("/v1/datalab/search")
    assert body["keywordGroups"] == [{"groupName": "발라클라바", "keywords": ["발라클라바"]}]
    assert body["gender"] == "f" and body["ages"] == ["4", "5"]
    assert s.headers["X-Naver-Client-Id"] == "id"


def test_segments_are_stored_separately(tmp_path):
    """전체 시계열과 성별 분해가 같은 행으로 뭉개지면 안 된다."""
    conn = storage.connect(tmp_path / "t.sqlite")
    storage.init_db(conn)
    for gender in (None, "f"):
        s = FakeSession([SEARCH_RESPONSE])
        c = NaverDataLabCollector("id", "secret", min_interval_sec=0, session=s)
        storage.insert_raw(conn, c.collect({"발라클라바": ["발라클라바"]},
                                           "2024-10-01", "2024-10-03", gender=gender))
    assert conn.execute("SELECT COUNT(*) FROM signal_raw").fetchone()[0] == 6
    entities = {r[0] for r in conn.execute("SELECT DISTINCT entity FROM signal_raw")}
    assert entities == {"", "gender=f"}


def test_api_error_is_raised_with_context():
    s = FakeSession([{"__status": 401, "errorMessage": "Not Exist Client ID"}])
    c = NaverDataLabCollector("bad", "bad", min_interval_sec=0, session=s)
    with pytest.raises(NaverApiError) as exc:
        list(c.collect({"a": ["a"]}, "2024-10-01", "2024-10-03"))
    assert exc.value.status == 401
    assert "/v1/datalab/search" in str(exc.value)


def test_keyword_group_limits_rejected():
    c = NaverDataLabCollector("id", "secret", min_interval_sec=0, session=FakeSession([]))
    with pytest.raises(ValueError, match="최대 5개"):
        list(c.collect({f"g{i}": ["k"] for i in range(6)}, "2024-10-01", "2024-10-03"))
    with pytest.raises(ValueError, match="최대 20개"):
        list(c.collect({"g": [f"k{i}" for i in range(21)]}, "2024-10-01", "2024-10-03"))


DEMO_GENDER = {"results": [{"title": "티셔츠", "data": [
    {"period": "2024-10-01", "group": "f", "ratio": 62.0},
    {"period": "2024-10-01", "group": "m", "ratio": 38.0}]}]}
DEMO_AGE = {"results": [{"title": "티셔츠", "data": [
    {"period": "2024-10-01", "group": "20", "ratio": 55.0},
    {"period": "2024-10-01", "group": "30", "ratio": 45.0}]}]}


def test_shopping_demographics_split_by_group():
    s = FakeSession([DEMO_GENDER, DEMO_AGE])
    c = NaverShoppingCollector("id", "secret", min_interval_sec=0, session=s)
    rows = list(c.collect_keyword_demographics("50000167", "티셔츠",
                                               "2024-10-01", "2024-10-01"))
    assert {r.entity for r in rows} == {"gender=f", "gender=m", "age=20", "age=30"}
    assert all(r.channel == "naver_shopping" for r in rows)
    # 성별과 연령은 서로 다른 엔드포인트를 쓴다
    assert s.calls[0][0].endswith("/category/keyword/gender")
    assert s.calls[1][0].endswith("/category/keyword/age")


def test_shopping_generic_collect_refuses():
    c = NaverShoppingCollector("id", "secret", min_interval_sec=0, session=FakeSession([]))
    with pytest.raises(NotImplementedError, match="collect_category"):
        list(c.collect())
