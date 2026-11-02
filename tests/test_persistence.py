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
