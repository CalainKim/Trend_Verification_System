"""지속성 케이스 생성 검증.

가장 중요한 것은 누수 차단이다. 특징이 확인 구간을 엿보면 모델 성적이
실제보다 좋게 나오는데 오류는 나지 않아서 발견하기 어렵다. 구조로 막혔는지를
자료를 바꿔 가며 확인한다.
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trend_pipeline import persistence as ps, storage  # noqa: E402
from trend_pipeline.models import RawRecord  # noqa: E402


def mkseries(spec):
    """{상품: [(일자, 순위, 리뷰)]} 를 load_series 와 같은 모양으로 만든다."""
    out = {}
    for key, points in spec.items():
        out[key] = {}
        for day, rank, review in points:
            out[key][day] = {"rank": float(rank), "review_count": float(review),
                             "heart_count": 0.0, "name": key, "brand": "B",
                             "sale": 0.0, "is_new": False, "sold_out": False}
    return out


def days_from(start, n):
    d0 = date.fromisoformat(start)
    return [(d0 + timedelta(days=i)).isoformat() for i in range(n)]


@pytest.fixture()
def win():
    d = days_from("2026-10-01", 9)
    return ps.Window(base=d[:3], detect=d[3:6], hold=d[6:]), d


# ------------------------------------------------------------ 누수 차단

def test_rise_events_ignore_hold_window(win):
    """확인 구간을 바꿔도 상승 판정과 특징이 달라지면 안 된다."""
    w, d = win
    a = mkseries({"x": [(d[i], 50 if i < 3 else 20, 10) for i in range(9)]})
    b = mkseries({"x": [(d[i], 50 if i < 3 else 20, 10) for i in range(6)]
                        + [(d[i], 99, 10) for i in range(6, 9)]})
    ea = ps.rise_events(a, w)
    eb = ps.rise_events(b, w)
    assert len(ea) == len(eb) == 1
    assert ea[0].features() == eb[0].features()


def test_label_uses_hold_window(win):
    """같은 특징이라도 확인 구간이 다르면 정답은 달라져야 한다."""
    w, d = win
    kept = mkseries({"x": [(d[i], 50 if i < 3 else 20, 10) for i in range(9)]})
    lost = mkseries({"x": [(d[i], 50 if i < 3 else 20, 10) for i in range(6)]
                           + [(d[i], 50, 10) for i in range(6, 9)]})
    ev = ps.rise_events(kept, w)
    assert ps.label_events(kept, w, ev)["x"] == ps.PERSIST
    assert ps.label_events(lost, w, ps.rise_events(lost, w))["x"] == ps.FADE


# ------------------------------------------------------------ 판정 규칙

def test_rank_direction(win):
    """순위는 숫자가 작아질수록 상승이다."""
    w, d = win
    down = mkseries({"x": [(d[i], 20 if i < 3 else 50, 10) for i in range(9)]})
    assert ps.rise_events(down, w) == []


def test_min_rise_threshold(win):
    w, d = win
    small = mkseries({"x": [(d[i], 50 if i < 3 else 45, 10) for i in range(9)]})
    assert ps.rise_events(small, w) == []
    assert len(ps.rise_events(small, w, min_rise=3)) == 1


def test_unobserved_in_hold_is_not_labeled(win):
    """확인 구간에 자료가 없으면 채점할 수 없으므로 케이스가 아니다."""
    w, d = win
    gone = mkseries({"x": [(d[i], 50 if i < 3 else 20, 10) for i in range(6)]})
    ev = ps.rise_events(gone, w)
    assert len(ev) == 1
    assert ps.label_events(gone, w, ev) == {}


def test_brand_simultaneous_risers(win):
    """브랜드 단위 효과를 상품 단위 신호와 구분하려면 동시 상승 수가 필요하다."""
    w, d = win
    s = mkseries({f"x{j}": [(d[i], 50 if i < 3 else 20, 10) for i in range(9)]
                  for j in range(3)})
    ev = ps.rise_events(s, w)
    assert all(e.brand_risers == 3 for e in ev)


# ------------------------------------------------------------ 창과 기저율

def test_windows_do_not_overlap_when_step_is_span():
    d = days_from("2026-10-01", 30)
    ws = ps.windows(d, 3, 3, 3, step=9)
    seen = [day for w in ws for day in w.base + w.detect + w.hold]
    assert len(seen) == len(set(seen))


def test_windows_overlap_when_step_is_one():
    d = days_from("2026-10-01", 12)
    assert len(ps.windows(d, 3, 3, 3, step=1)) > len(ps.windows(d, 3, 3, 3, step=9))


def test_t_cut_is_last_detect_day(win):
    w, d = win
    assert w.t_cut == d[5]
    assert w.t_cut not in w.hold


def test_base_rate():
    assert ps.base_rate([ps.PERSIST] * 3 + [ps.FADE]) == 0.75
    assert ps.base_rate([]) is None


# ------------------------------------------------------------ 산출물

def test_features_contain_no_label(win):
    """문제지에 정답이 섞이면 채점이 무의미해진다."""
    w, d = win
    s = mkseries({"x": [(d[i], 50 if i < 3 else 20, 10) for i in range(9)]})
    f = ps.rise_events(s, w)[0].features()
    blob = json.dumps(f, ensure_ascii=False)
    assert ps.PERSIST not in blob and ps.FADE not in blob
    assert "label" not in blob


# ------------------------------------------------------------ 지수 시계열

def mkindex(spec):
    """{키워드: [(일자, 값)]} 를 load_index_series 와 같은 모양으로 만든다."""
    return {k: {d: float(v) for d, v in pts} for k, pts in spec.items()}


@pytest.fixture()
def iwin():
    d = days_from("2026-01-01", 9)
    return ps.Window(base=d[:3], detect=d[3:6], hold=d[6:]), d


def test_index_rise_is_measured_as_ratio(iwin):
    """지수는 정규화된 상대값이라 차이의 절대 크기에 뜻이 없다."""
    w, d = iwin
    small = mkindex({"a": [(d[i], 10 if i < 3 else 13) for i in range(9)]})
    big = mkindex({"b": [(d[i], 80 if i < 3 else 83) for i in range(9)]})
    assert len(ps.index_rise_events(small, w)) == 1     # 1.3배
    assert ps.index_rise_events(big, w) == []           # 같은 +3 이지만 1.04배


def test_index_rise_events_ignore_hold(iwin):
    w, d = iwin
    a = mkindex({"a": [(d[i], 10 if i < 3 else 15) for i in range(9)]})
    b = mkindex({"a": [(d[i], 10 if i < 3 else 15) for i in range(6)]
                       + [(d[i], 1) for i in range(6, 9)]})
    ea, eb = ps.index_rise_events(a, w), ps.index_rise_events(b, w)
    assert ea[0].features() == eb[0].features()


def test_index_label_uses_hold(iwin):
    w, d = iwin
    kept = mkindex({"a": [(d[i], 10 if i < 3 else 15) for i in range(9)]})
    lost = mkindex({"a": [(d[i], 10 if i < 3 else 15) for i in range(6)]
                          + [(d[i], 10) for i in range(6, 9)]})
    assert ps.label_index_events(kept, w, ps.index_rise_events(kept, w))["a"] == ps.PERSIST
    assert ps.label_index_events(lost, w, ps.index_rise_events(lost, w))["a"] == ps.FADE


def test_low_coverage_is_skipped(iwin):
    """결측이 많은 구간에서 추세를 읽으면 안 된다."""
    w, d = iwin
    sparse = mkindex({"a": [(d[0], 10), (d[3], 15)]})
    assert ps.index_rise_events(sparse, w) == []


def test_mixed_normalization_window_series_is_dropped(tmp_path):
    """창이 다른 값을 이으면 이음새의 계단을 상승으로 읽는다."""
    from trend_pipeline import storage
    from trend_pipeline.models import RawRecord
    c = storage.connect(tmp_path / "i.sqlite")
    storage.init_db(c)
    d0 = date.fromisoformat("2026-01-01")
    recs = []
    for i in range(10):
        w = "2026-01-01 ~ 2026-06-01" if i < 5 else "2026-01-01 ~ 2026-09-01"
        recs.append(RawRecord(channel="gtrends", keyword_raw="mixed",
                              entity="geo=KR", metric_type="search_index",
                              metric_value=50.0,
                              observed_at=(d0 + timedelta(days=i)).isoformat(),
                              metadata={"query_start": w.split(" ~ ")[0],
                                        "query_end": w.split(" ~ ")[1]}))
    for i in range(10):
        recs.append(RawRecord(channel="gtrends", keyword_raw="clean",
                              entity="geo=KR", metric_type="search_index",
                              metric_value=50.0,
                              observed_at=(d0 + timedelta(days=i)).isoformat(),
                              metadata={"query_start": "2026-01-01",
                                        "query_end": "2026-06-01"}))
    storage.insert_raw(c, recs)
    s = ps.load_index_series(c, "gtrends", ["geo=KR"])
    assert "clean@geo=KR" in s
    assert "mixed@geo=KR" not in s
    c.close()


def test_yoy_ratio_detects_repeating_season():
    """해마다 같은 시기에 오르면 전년 대비가 1 에 가깝다."""
    d0 = date.fromisoformat("2024-01-01")
    item = {}
    for i in range(800):
        day = (d0 + timedelta(days=i)).isoformat()
        item[day] = 100.0 if (i % 365) < 30 else 20.0
    this_year = [(d0 + timedelta(days=i + 730)).isoformat() for i in range(20)]
    r = ps.yoy_ratio(item, this_year)
    assert r is not None and 0.9 <= r <= 1.1


def test_yoy_ratio_detects_new_rise():
    d0 = date.fromisoformat("2024-01-01")
    item = {}
    for i in range(800):
        day = (d0 + timedelta(days=i)).isoformat()
        item[day] = 80.0 if i >= 730 else 20.0
    this_year = [(d0 + timedelta(days=i + 730)).isoformat() for i in range(20)]
    assert ps.yoy_ratio(item, this_year) == pytest.approx(4.0)


def test_yoy_ratio_is_none_without_prior_year():
    """자료가 없으면 억지로 메우지 않는다. 메우면 계절성이 없다고 잘못 읽는다."""
    d0 = date.fromisoformat("2026-01-01")
    item = {(d0 + timedelta(days=i)).isoformat(): 50.0 for i in range(30)}
    days = [(d0 + timedelta(days=i)).isoformat() for i in range(10)]
    assert ps.yoy_ratio(item, days) is None


# ------------------------------------------------------- 여러 entity

def test_series_key_roundtrip():
    assert ps.split_series_key(ps.series_key("헨리넥", "geo=KR")) == ("헨리넥", "geo=KR")
    assert ps.split_series_key(ps.series_key("헨리넥", "")) == ("헨리넥", "")


def _seed_index(conn, keyword, entity, values, start="2026-01-01",
                window=("2026-01-01", "2026-12-31")):
    from trend_pipeline import storage
    from trend_pipeline.models import RawRecord
    d0 = date.fromisoformat(start)
    storage.insert_raw(conn, [
        RawRecord(channel="gtrends", keyword_raw=keyword, entity=entity,
                  metric_type="search_index", metric_value=float(v),
                  observed_at=(d0 + timedelta(days=i)).isoformat(),
                  metadata={"query_start": window[0], "query_end": window[1]})
        for i, v in enumerate(values)])


@pytest.fixture()
def idx_conn(tmp_path):
    from trend_pipeline import storage
    c = storage.connect(tmp_path / "x.sqlite")
    storage.init_db(c)
    yield c
    c.close()


def test_entities_make_separate_series(idx_conn):
    """같은 키워드라도 지역이 다르면 다른 사건이다."""
    _seed_index(idx_conn, "kw", "geo=KR", [10] * 9)
    _seed_index(idx_conn, "kw", "geo=US", [20] * 9)
    s = ps.load_index_series(idx_conn, "gtrends", ["geo=KR", "geo=US"])
    assert set(s) == {"kw@geo=KR", "kw@geo=US"}
    assert s["kw@geo=KR"][list(s["kw@geo=KR"])[0]] == 10.0


def test_single_entity_still_works(idx_conn):
    _seed_index(idx_conn, "kw", "geo=KR", [10] * 9)
    s = ps.load_index_series(idx_conn, "gtrends", ["geo=KR"])
    assert set(s) == {"kw@geo=KR"}


def test_mixed_window_drops_only_that_entity(idx_conn):
    """한 지역의 창이 섞였다고 다른 지역까지 버리면 안 된다."""
    _seed_index(idx_conn, "kw", "geo=KR", [10] * 5)
    _seed_index(idx_conn, "kw", "geo=KR", [10] * 4, start="2026-01-06",
                window=("2026-01-01", "2026-09-01"))
    _seed_index(idx_conn, "kw", "geo=US", [20] * 9)
    s = ps.load_index_series(idx_conn, "gtrends", ["geo=KR", "geo=US"])
    assert "kw@geo=KR" not in s
    assert "kw@geo=US" in s


def test_event_keeps_keyword_and_entity(idx_conn):
    """번들에는 지역을 뺀 키워드를 싣는다. 모델이 읽을 이름이기 때문이다."""
    _seed_index(idx_conn, "헨리넥", "geo=KR", [10, 10, 10, 15, 15, 15, 15, 15, 15])
    s = ps.load_index_series(idx_conn, "gtrends", ["geo=KR"])
    d = sorted(list(s.values())[0])
    w = ps.Window(base=d[:3], detect=d[3:6], hold=d[6:])
    ev = ps.index_rise_events(s, w)
    assert len(ev) == 1
    assert ev[0].keyword == "헨리넥"
    assert ev[0].entity == "geo=KR"
    assert ev[0].key == "헨리넥@geo=KR"


# ------------------------------------------------------- 옛 케이스 정리

def test_rebuild_removes_cases_from_old_window_config(idx_conn, tmp_path):
    """창 구성을 바꾸면 케이스 id 가 달라진다. 옛 파일을 남기면 문제지가
    정답보다 많아지고, 검증 파트는 채점할 수 없는 케이스를 돌리게 된다."""
    import json
    import sys as _sys
    _sys.path.insert(0, str(ROOT / "scripts"))
    import build_persistence_cases as bpc

    vals = [10, 10, 10, 10, 20, 20, 20, 20, 20, 20, 20, 20,
            20, 20, 20, 20, 20, 20, 20, 20]
    _seed_index(idx_conn, "kw", "geo=KR", vals)
    out = tmp_path / "bench"
    db = str(tmp_path / "x.sqlite")

    bpc.main(["--source", "index", "--db", db, "--entities", "geo=KR",
              "--base", "3", "--detect", "2", "--hold", "3", "--step", "8",
              "--out", str(out)])
    first = {f.stem for f in (out / "cases").glob("*.json")}

    bpc.main(["--source", "index", "--db", db, "--entities", "geo=KR",
              "--base", "4", "--detect", "2", "--hold", "4", "--step", "10",
              "--out", str(out)])
    second = {f.stem for f in (out / "cases").glob("*.json")}
    labels = set(json.loads((out / "labels.sealed.json").read_text(
        encoding="utf-8"))["labels"])

    assert second == labels            # 문제지와 정답이 어긋나지 않는다
    assert not (first - second) or first != second


class TestWindowYoy:
    """커머스 창(일별)과 검색 지수(주별)는 격자가 다르다.

    yoy_ratio 를 그대로 쓰면 일별 날짜로 주별 자료를 찾아 전부 빗나간다.
    조용히 None 만 돌려주므로 터지지 않고 넘어간다. 그래서 여기서 막는다.
    """

    def test_matches_weekly_data_from_daily_window(self):
        from trend_pipeline.persistence import window_yoy

        item = {"2025-10-05": 10.0, "2025-10-12": 10.0,
                "2026-10-04": 20.0, "2026-10-11": 20.0}
        days = [f"2026-10-{d:02d}" for d in range(6, 13)]
        assert window_yoy(item, days) == pytest.approx(2.0)

    def test_old_helper_misses_on_mismatched_grid(self):
        from trend_pipeline.persistence import window_yoy, yoy_ratio

        item = {"2025-10-05": 10.0, "2025-10-12": 10.0,
                "2026-10-04": 20.0, "2026-10-11": 20.0}
        days = [f"2026-10-{d:02d}" for d in range(6, 13)]
        # 일별 날짜가 주별 자료에 없어 격자가 다른 쪽은 답을 못 낸다.
        assert yoy_ratio(item, days) is None
        assert window_yoy(item, days) is not None

    def test_no_last_year_returns_none(self):
        from trend_pipeline.persistence import window_yoy

        item = {"2026-10-04": 20.0, "2026-10-11": 20.0}
        days = [f"2026-10-{d:02d}" for d in range(6, 13)]
        assert window_yoy(item, days) is None

    def test_zero_last_year_is_not_infinite(self):
        from trend_pipeline.persistence import window_yoy

        item = {"2025-10-05": 0.0, "2026-10-04": 20.0}
        days = [f"2026-10-{d:02d}" for d in range(6, 13)]
        assert window_yoy(item, days) is None


class TestMissingDayMeaning:
    """창에 빈 날이 있으면 그게 무슨 뜻인지 밝혀야 한다.

    창은 observed_days 로 고른 날만 쓴다. 그러니 창에 적힌 날은 전부 수집이
    있었던 날이고, 그 상품이 없다는 것은 자료가 없다는 뜻이 아니라 그날
    TOP100 밖으로 떨어졌다는 뜻이다. 기준 시점 직전에 밖에 있었다면 버티지
    못했다는 강한 신호다.

    그런데 이걸 "결측" 이라고 적어 보내고 있었다. 모델은 자료가 없는 것으로
    읽고 판단을 보류했다. 4차 실행에서 기권 37건이 든 이유를 세어 보니 광고
    여부 36회 다음으로 많은 것이 이 빈 날이었고 28회였다. 신호를 가지고
    있으면서 잡음이라고 적어 보낸 셈이다.
    """

    def _event(self, ranks):
        """상품 하나가 아홉 날 중 일부에만 있는 창을 만든다."""
        d = days_from("2026-10-01", 9)
        pts = [(day, r, 10) for day, r in zip(d, ranks) if r is not None]
        # 혼자면 그날 수집이 있었는지 알 수 없다. 늘 있는 상품을 하나 둔다.
        series = mkseries({"A": pts, "B": [(day, 50, 10) for day in d]})
        w = ps.Window(base=d[:3], detect=d[3:6], hold=d[6:])
        events = {e.item_key: e for e in ps.rise_events(series, w, min_rise=1.0)}
        return events.get("A"), w

    def test_absent_day_is_called_out_of_top100(self):
        e, w = self._event([80, None, 78, 50, 52, 48, None, None, None])
        assert e is not None
        line = next(x for x in e.evidence(w) if x["id"] == "rank_daily")
        assert "TOP100 밖" in line["observation"]
        assert "결측" not in line["observation"]

    def test_says_why_it_is_not_missing_data(self):
        """단어만 바꾸면 모델이 또 자료 없음으로 읽는다. 이유를 적는다."""
        e, w = self._event([80, None, 78, 50, 52, 48, None, None, None])
        line = next(x for x in e.evidence(w) if x["id"] == "rank_daily")
        assert "수집이 있었던" in line["observation"]

    def test_does_not_look_at_the_hold_window(self):
        """확인 구간은 근거에도 특징에도 들어가면 안 된다. 그게 정답이다."""
        a, wa = self._event([80, 82, 78, 50, 52, 48, None, None, None])
        b, wb = self._event([80, 82, 78, 50, 52, 48, 40, 41, 42])
        assert a.features() == b.features()
        assert a.evidence(wa) == b.evidence(wb)

    def test_adds_no_summary_number(self):
        """밖에 있던 날 수를 특징으로 넣지 않는다.

        넣어 보고 정답과 맞춰 보니 전체 날수로는 신호가 없었고(0일 60%,
        1~3일 50%, 4일 이상 54%, 기저율 54%), t_cut 직전 연속 날수로는
        있었다(0일 63%, 1~2일 43%, 3일 이상 17%). 그런데 뒤의 것은 채점에
        쓸 바로 그 61건의 정답을 보고 고른 것이라, 같은 문제지에서 올라간
        점수는 부풀려진 값이다. 일별 순위를 그대로 주면 모델이 읽을 수
        있으므로 요약 숫자는 넣지 않는다. 수집이 쌓여 새 문제지가 나오면
        그때 확인한다.
        """
        e, _ = self._event([80, None, 78, 50, None, 48, None, None, None])
        assert "days_out_of_top100" not in e.features()
        assert set(e.features()) == {
            "rank_base", "rank_at_cut", "rank_rise", "review_delta",
            "heart_delta", "sale_percent_delta", "is_new", "sold_out",
            "brand_simultaneous_risers"}


class TestCalendarGaps:
    """창에 적힌 날 사이에 수집이 통째로 없던 날은 따로 알려야 한다.

    창은 수집이 있었던 날을 이어 붙인 것이라 10-16 다음이 10-18 일 수 있다.
    그 사이 10-17 은 상품이 밖에 있던 것이 아니라 아무도 수집하지 않은
    날이다. TOP100 밖 과 한 단어로 적으면 같은 혼동이 반대로 생긴다.
    """

    def test_finds_the_skipped_day(self):
        assert ps._calendar_gaps(["2026-10-16", "2026-10-18"]) == ["10-17"]

    def test_finds_several(self):
        assert ps._calendar_gaps(["2026-10-16", "2026-10-20"]) == [
            "10-17", "10-18", "10-19"]

    def test_consecutive_days_have_none(self):
        assert ps._calendar_gaps(["2026-10-16", "2026-10-17"]) == []

    def test_mentioned_in_the_evidence(self):
        d = ["2026-10-01", "2026-10-02", "2026-10-03",
             "2026-10-04", "2026-10-06", "2026-10-07"]      # 10-05 수집 없음
        hold = ["2026-10-08", "2026-10-09", "2026-10-10"]
        series = mkseries({"A": [(x, r, 10) for x, r in zip(d + hold, [80, 82, 78, 50, 52, 48, 40, 41, 42])],
                           "B": [(x, 50, 10) for x in d + hold]})
        w = ps.Window(base=d[:3], detect=d[3:], hold=hold)
        e = next(x for x in ps.rise_events(series, w, min_rise=1.0)
                 if x.item_key == "A")
        line = next(x for x in e.evidence(w) if x["id"] == "rank_daily")
        assert "10-05" in line["observation"]
        assert "수집 자체가 없어" in line["observation"]
