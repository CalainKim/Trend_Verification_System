"""해외 선행 계산 검증. 네트워크를 쓰지 않는다."""

from __future__ import annotations

import math
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trend_pipeline import features as ft, storage  # noqa: E402
from trend_pipeline.models import RawRecord  # noqa: E402


@pytest.fixture()
def conn(tmp_path):
    c = storage.connect(tmp_path / "g.sqlite")
    storage.init_db(c)
    yield c
    c.close()


def _wave(conn, keyword, geo, shift_days, days=200, start="2026-01-01", noise=0.0):
    """해외가 shift_days 만큼 앞선 파형을 심는다."""
    d0 = date.fromisoformat(start)
    recs = []
    for i in range(days):
        v = math.sin((i + shift_days) / 12) * 50 + 50 + (i % 3) * noise
        recs.append(RawRecord(
            channel="gtrends", keyword_raw=keyword, entity=f"geo={geo}",
            metric_type="search_index", metric_value=v,
            observed_at=(d0 + timedelta(days=i)).isoformat()))
    storage.insert_raw(conn, recs)


def test_recovers_planted_lead(conn):
    _wave(conn, "kw", "KR", 0)
    _wave(conn, "kw", "US", 10)      # 해외가 10일 앞섬
    ll = ft.lead_lag(conn, "kw", "2026-06-01", "US")
    assert ll.lead_days == 10
    assert ll.correlation > 0.99
    assert ll.reliable


def test_detects_home_leading(conn):
    _wave(conn, "kw", "KR", 14)
    _wave(conn, "kw", "US", 0)
    ll = ft.lead_lag(conn, "kw", "2026-06-01", "US")
    assert ll.lead_days == -14      # 음수면 한국이 앞선 것


def test_boundary_hit_is_not_reliable(conn):
    """최적값이 탐색 범위 끝에 걸리면 진짜 최적은 범위 밖일 수 있다."""
    _wave(conn, "kw", "KR", 0)
    _wave(conn, "kw", "US", 10)
    ll = ft.lead_lag(conn, "kw", "2026-06-01", "US", max_shift=10)
    assert ll.lead_days == 10
    assert ll.at_boundary
    assert not ll.reliable          # 상관이 완벽해도 경계면 신뢰 불가


def test_low_correlation_is_not_reliable(conn):
    _wave(conn, "kw", "KR", 0)
    d0 = date.fromisoformat("2026-01-01")
    storage.insert_raw(conn, [
        RawRecord(channel="gtrends", keyword_raw="kw", entity="geo=US",
                  metric_type="search_index", metric_value=(i * 37 % 97),
                  observed_at=(d0 + timedelta(days=i)).isoformat())
        for i in range(200)])
    ll = ft.lead_lag(conn, "kw", "2026-06-01", "US")
    assert ll.correlation < ft.MIN_LEAD_CORRELATION or not ll.reliable


def test_as_of_excludes_later_data(conn):
    _wave(conn, "kw", "KR", 0, days=400)
    _wave(conn, "kw", "US", 10, days=400)
    early = ft.lead_lag(conn, "kw", "2026-05-01", "US", window_days=120)
    assert early.n_overlap < 200        # 창 밖 자료가 섞이지 않았다


def test_missing_geo_returns_none(conn):
    _wave(conn, "kw", "KR", 0)
    assert ft.lead_lag(conn, "kw", "2026-06-01", "US") is None


# ---------------------------------------------------------------- 속성 분리

def test_web_entity_keeps_old_shape():
    """웹 검색에 접미사를 붙이면 이미 쌓인 자료가 조회에서 빠진다."""
    from trend_pipeline.models import geo_entity
    assert geo_entity("KR") == "geo=KR"
    assert geo_entity("") == "geo=WORLD"


def test_youtube_entity_is_separate():
    from trend_pipeline.models import geo_entity
    assert geo_entity("KR", "youtube") == "geo=KR;prop=youtube"
    assert geo_entity("KR", "youtube") != geo_entity("KR")


def test_unknown_prop_rejected():
    from trend_pipeline.models import geo_entity
    with pytest.raises(ValueError):
        geo_entity("KR", "tiktok")


def _wave_prop(conn, keyword, geo, shift_days, gprop, days=200, start="2026-01-01"):
    from trend_pipeline.models import geo_entity
    d0 = date.fromisoformat(start)
    storage.insert_raw(conn, [
        RawRecord(channel="gtrends", keyword_raw=keyword,
                  entity=geo_entity(geo, gprop), metric_type="search_index",
                  metric_value=math.sin((i + shift_days) / 12) * 50 + 50,
                  observed_at=(d0 + timedelta(days=i)).isoformat())
        for i in range(days)])


def test_youtube_and_web_do_not_mix(conn):
    """같은 키워드라도 속성이 다르면 서로 섞이면 안 된다."""
    _wave_prop(conn, "kw", "KR", 0, "")
    _wave_prop(conn, "kw", "US", 7, "")          # 웹은 해외가 7일 앞섬
    _wave_prop(conn, "kw", "KR", 0, "youtube")
    _wave_prop(conn, "kw", "US", 21, "youtube")  # 유튜브는 21일 앞섬

    web = ft.lead_lag(conn, "kw", "2026-06-01", "US")
    yt = ft.lead_lag(conn, "kw", "2026-06-01", "US", gprop="youtube")
    assert web.lead_days == 7
    assert yt.lead_days == 21


def test_missing_prop_returns_none(conn):
    """웹만 쌓였는데 유튜브를 물으면 없다고 답해야 한다."""
    _wave_prop(conn, "kw", "KR", 0, "")
    _wave_prop(conn, "kw", "US", 7, "")
    assert ft.lead_lag(conn, "kw", "2026-06-01", "US", gprop="youtube") is None


def test_search_window_covers_order_lead_time():
    """재고 확보와 발주가 8~12주 앞에 일어난다. 탐색 범위가 그보다 좁으면
    정작 실무에 필요한 구간을 보지 못한다."""
    assert ft.MAX_LEAD_DAYS >= 84
    assert ft.MAX_LEAD_DAYS <= 90      # 한 계절을 넘기면 다른 유행이 겹친다


# ------------------------------------------------------- 정규화 창 혼합

def _wave_window(conn, keyword, geo, shift_days, q_start, q_end, days=120):
    """질의 창을 명시해 파형을 심는다."""
    d0 = date.fromisoformat("2026-01-01")
    storage.insert_raw(conn, [
        RawRecord(channel="gtrends", keyword_raw=keyword, entity=f"geo={geo}",
                  metric_type="search_index",
                  metric_value=math.sin((i + shift_days) / 12) * 50 + 50,
                  observed_at=(d0 + timedelta(days=i)).isoformat(),
                  metadata={"query_start": q_start, "query_end": q_end})
        for i in range(days)])


def test_single_query_window_is_fine(conn):
    _wave_window(conn, "kw", "KR", 0, "2026-01-01", "2026-06-01")
    _wave_window(conn, "kw", "US", 10, "2026-01-01", "2026-06-01")
    ll = ft.lead_lag(conn, "kw", "2026-05-01", "US")
    assert ll.lead_days == 10


def test_mixed_query_windows_are_rejected(conn):
    """창이 다르면 분모가 다르다. 이어 붙이면 없던 계단이 생긴다."""
    _wave_window(conn, "kw", "KR", 0, "2026-01-01", "2026-06-01", days=60)
    storage.insert_raw(conn, [
        RawRecord(channel="gtrends", keyword_raw="kw", entity="geo=KR",
                  metric_type="search_index", metric_value=50.0,
                  observed_at=(date.fromisoformat("2026-01-01")
                               + timedelta(days=i)).isoformat(),
                  metadata={"query_start": "2026-01-01", "query_end": "2026-09-01"})
        for i in range(60, 120)])
    _wave_window(conn, "kw", "US", 10, "2026-01-01", "2026-06-01")
    with pytest.raises(ft.MixedQueryWindow):
        ft.lead_lag(conn, "kw", "2026-05-01", "US")


# ------------------------------------------------------- 신뢰 문턱

def test_threshold_is_strict_enough():
    """0.3 은 너무 느슨했다. 상관 0.35 짜리가 선행 근거로 통과했다."""
    assert ft.MIN_LEAD_CORRELATION >= 0.5


def test_weak_correlation_rejected_at_new_threshold(conn):
    """같은 자료라도 문턱이 올라가면 걸러져야 한다."""
    d0 = date.fromisoformat("2026-01-01")
    _wave(conn, "kw", "KR", 0, days=300)
    storage.insert_raw(conn, [
        RawRecord(channel="gtrends", keyword_raw="kw", entity="geo=US",
                  metric_type="search_index",
                  metric_value=math.sin(i / 12) * 15 + 50 + (i * 29 % 61),
                  observed_at=(d0 + timedelta(days=i)).isoformat())
        for i in range(300)])
    ll = ft.lead_lag(conn, "kw", "2026-09-01", "US")
    if ll is not None and ll.correlation < 0.5:
        assert not ll.reliable


# ------------------------------------------------------- 창 고르기

def _win_rows(conn, keyword, geo, q_start, q_end, value, days, offset=0):
    d0 = date.fromisoformat("2026-01-01")
    storage.insert_raw(conn, [
        RawRecord(channel="gtrends", keyword_raw=keyword, entity=f"geo={geo}",
                  metric_type="search_index", metric_value=value(i),
                  observed_at=(d0 + timedelta(days=i + offset)).isoformat(),
                  metadata={"query_start": q_start, "query_end": q_end})
        for i in range(days)])


def test_available_windows_lists_by_row_count(conn):
    _win_rows(conn, "kw", "KR", "2026-01-01", "2026-06-01",
              lambda i: 50.0, 80)
    _win_rows(conn, "kw", "KR", "2026-01-01", "2026-09-01",
              lambda i: 50.0, 20, offset=80)
    ws = ft.available_windows(conn, "kw", "KR")
    assert ws[0] == "2026-01-01 ~ 2026-06-01"      # 행이 많은 쪽이 앞
    assert len(ws) == 2


def test_query_window_lets_analysis_proceed_without_deleting(conn):
    """자료를 지우지 않고도 창 하나를 골라 분석할 수 있어야 한다."""
    good = "2026-01-01 ~ 2026-06-01"
    _win_rows(conn, "kw", "KR", good, "", lambda i: math.sin(i / 12) * 50 + 50, 150)
    _win_rows(conn, "kw", "US", good, "",
              lambda i: math.sin((i + 10) / 12) * 50 + 50, 150)
    # 창이 다른 자료를 덧붙인다
    _win_rows(conn, "kw", "KR", "2026-01-01", "2026-09-01",
              lambda i: 99.0, 30, offset=150)

    with pytest.raises(ft.MixedQueryWindow):
        ft.lead_lag(conn, "kw", "2026-06-01", "US")

    # 없는 창을 지정하면 자료가 비므로 결과가 없어야 한다
    assert ft.lead_lag(conn, "kw", "2026-06-01", "US",
                       query_window="1999-01-01 ~ 1999-12-31") is None

    picked = ft.available_windows(conn, "kw", "KR")[0]
    ll = ft.lead_lag(conn, "kw", "2026-06-01", "US", query_window=picked)
    assert ll is not None and ll.lead_days == 10


# ------------------------------------------------------- 429 재시도

def test_rate_limit_detection():
    from trend_pipeline.collectors import gtrends as g
    assert g.is_rate_limited("TooManyRequestsError: code 429")
    assert g.is_rate_limited("Google returned a response with code 429")
    assert not g.is_rate_limited("ConnectionError: dns resolution failed")
    assert not g.is_rate_limited("ValueError: bad payload")


def test_rate_limit_waits_minutes_not_seconds(monkeypatch):
    """429 에 5초 재시도는 소용이 없었다. 분 단위로 기다려야 한다."""
    from trend_pipeline.collectors import gtrends as g

    slept = []
    monkeypatch.setattr(g.time, "sleep", lambda s: slept.append(s))
    col = g.GoogleTrendsCollector(max_attempts=3)
    monkeypatch.setattr(col, "sleep", lambda: None)

    def boom(*a, **k):
        raise RuntimeError("The request failed: Google returned a response with code 429")
    monkeypatch.setattr(col, "_fresh_client", boom)

    with pytest.raises(g.GoogleTrendsUnavailable):
        col._fetch(["kw"], "2026-01-01 2026-06-01", "KR")

    waits = [s for s in slept if s >= g.RATE_LIMIT_BACKOFF_SEC]
    assert len(waits) == 2                      # 마지막 시도 뒤에는 안 기다린다
    assert waits == [g.RATE_LIMIT_BACKOFF_SEC, g.RATE_LIMIT_BACKOFF_SEC * 2]
    assert col._throttled


def test_transient_error_keeps_short_backoff(monkeypatch):
    """네트워크 끊김은 429 와 다르다. 길게 기다릴 이유가 없다."""
    from trend_pipeline.collectors import gtrends as g

    slept = []
    monkeypatch.setattr(g.time, "sleep", lambda s: slept.append(s))
    col = g.GoogleTrendsCollector(max_attempts=3)
    monkeypatch.setattr(col, "sleep", lambda: None)
    monkeypatch.setattr(col, "_fresh_client",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("dns fail")))

    with pytest.raises(g.GoogleTrendsUnavailable):
        col._fetch(["kw"], "2026-01-01 2026-06-01", "KR")

    assert slept == [g.RETRY_BACKOFF_SEC, g.RETRY_BACKOFF_SEC * 2]
    assert not col._throttled
