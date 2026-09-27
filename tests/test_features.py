"""특징 추출 검증. 핵심은 as_of 이후 데이터가 절대 섞이지 않는 것이다."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trend_pipeline import features as ft, storage  # noqa: E402
from trend_pipeline.models import RawRecord  # noqa: E402


@pytest.fixture()
def conn(tmp_path):
    c = storage.connect(tmp_path / "f.sqlite")
    storage.init_db(c)
    yield c
    c.close()


def _fill(conn, keyword, start, values, channel="naver_datalab",
          entity="", metric="search_index"):
    d0 = date.fromisoformat(start)
    storage.insert_raw(conn, [
        RawRecord(channel=channel, keyword_raw=keyword, entity=entity,
                  metric_type=metric, metric_value=v,
                  observed_at=(d0 + timedelta(days=i)).isoformat())
        for i, v in enumerate(values)])


def test_rising_series_gives_ratio_above_one(conn):
    # 28일 낮게, 7일 높게
    _fill(conn, "kw", "2026-07-01", [10.0] * 28 + [40.0] * 7)
    t = ft.channel_trend(conn, "kw", "naver_datalab", "", "2026-08-05")
    assert t.change_ratio == pytest.approx(4.0)
    assert t.coverage == pytest.approx(1.0)


def test_as_of_excludes_later_data(conn):
    """as_of 이후 값이 특징에 영향을 주면 안 된다.

    누수 차단이 내보내기 단계에만 있으면 특징 계산이 미래를 본 순간 오염된다.
    """
    _fill(conn, "kw", "2026-07-01", [10.0] * 35)
    before = ft.channel_trend(conn, "kw", "naver_datalab", "", "2026-08-05")
    # as_of 이후에 폭등이 있었다고 넣는다
    _fill(conn, "kw", "2026-08-05", [999.0] * 10)
    after = ft.channel_trend(conn, "kw", "naver_datalab", "", "2026-08-05")
    assert before.change_ratio == after.change_ratio
    assert after.last_value == 10.0


def test_slope_sign_follows_direction(conn):
    _fill(conn, "kw", "2026-07-01", [10.0] * 28 + [10, 20, 30, 40, 50, 60, 70])
    up = ft.channel_trend(conn, "kw", "naver_datalab", "", "2026-08-05")
    assert up.slope > 0
    _fill(conn, "kw2", "2026-07-01", [10.0] * 28 + [70, 60, 50, 40, 30, 20, 10])
    down = ft.channel_trend(conn, "kw2", "naver_datalab", "", "2026-08-05")
    assert down.slope < 0


def test_single_channel_is_flagged(conn):
    _fill(conn, "kw", "2026-07-01", [10.0] * 35)
    f = ft.extract(conn, "kw", "2026-08-05")
    assert f.channel_count == 1
    assert any("교차검증이 성립하지 않는다" in n for n in f.notes)


def test_two_channels_counted(conn):
    _fill(conn, "kw", "2026-07-01", [10.0] * 35)
    _fill(conn, "kw", "2026-07-01", [5.0] * 35,
          channel="naver_shopping", metric="click_index")
    f = ft.extract(conn, "kw", "2026-08-05")
    assert f.channel_count == 2
    assert not any("교차검증" in n for n in f.notes)


def test_missing_data_returns_none(conn):
    assert ft.channel_trend(conn, "없음", "naver_datalab", "", "2026-08-05") is None


def test_save_roundtrip(conn):
    _fill(conn, "kw", "2026-07-01", [10.0] * 35)
    conn.execute("INSERT INTO signal_candidate"
                 "(candidate_id, canonical_keyword, first_detected_at, created_at)"
                 " VALUES ('c1','kw','2026-07-01','2026-08-05')")
    f = ft.extract(conn, "kw", "2026-08-05")
    ft.save(conn, "c1", f)
    row = conn.execute("SELECT * FROM candidate_summary WHERE candidate_id='c1'").fetchone()
    assert row["date"] == "2026-08-05"
    assert row["channel_count"] == 1
    assert "럭비" not in row["demographic_distribution"]
