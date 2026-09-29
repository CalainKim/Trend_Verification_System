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
