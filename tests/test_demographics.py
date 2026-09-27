"""인구통계 쏠림 계산 검증."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trend_pipeline import demographics as dg, storage  # noqa: E402
from trend_pipeline.models import RawRecord  # noqa: E402


@pytest.fixture()
def conn(tmp_path):
    c = storage.connect(tmp_path / "d.sqlite")
    storage.init_db(c)
    yield c
    c.close()


def _rows(conn, keyword, per_day):
    """per_day: {날짜: {그룹: 지수}}"""
    recs = []
    for day, groups in per_day.items():
        for g, v in groups.items():
            recs.append(RawRecord(
                channel="naver_shopping", keyword_raw=keyword, entity=f"age={g}",
                metric_type="click_index", metric_value=v, observed_at=day))
    storage.insert_raw(conn, recs)


def test_shares_sum_to_one(conn):
    _rows(conn, "kw", {
        "2026-08-01": {"20": 30.0, "30": 70.0},
        "2026-08-02": {"20": 50.0, "30": 50.0},
    })
    shares = dg.daily_shares(conn, "kw", "age")
    assert sum(shares.values()) == pytest.approx(1.0)
    assert shares["20"] == pytest.approx(0.4)   # (0.3 + 0.5) / 2


def test_missing_group_counts_as_zero(conn):
    """다른 그룹에 데이터가 있는 날 빠진 그룹은 0 이다.

    '있던 날'만 평균내면 희소한 그룹의 점유율이 부풀려진다. 그 그룹이 나타난
    날은 당연히 점유율이 높은 날이기 때문이다.
    """
    _rows(conn, "kw", {
        "2026-08-01": {"10": 100.0},              # 10대만 있던 날
        "2026-08-02": {"20": 50.0, "30": 50.0},
        "2026-08-03": {"20": 50.0, "30": 50.0},
        "2026-08-04": {"20": 50.0, "30": 50.0},
    })
    shares = dg.daily_shares(conn, "kw", "age")
    assert sum(shares.values()) == pytest.approx(1.0)
    assert shares["10"] == pytest.approx(0.25)    # 4일 중 하루만 100% -> 25%
    assert shares["10"] < 1.0                      # 빠진 날을 건너뛰면 1.0 이 된다


def test_lift_against_baseline(conn):
    _rows(conn, "kw", {"2026-08-01": {"20": 40.0, "40": 60.0}})
    _rows(conn, "category:50000169", {"2026-08-01": {"20": 10.0, "40": 90.0}})
    skews = {s.group: s for s in dg.profile(conn, "kw", "50000169")}
    assert skews["20"].lift == pytest.approx(4.0)   # 0.4 / 0.1
    assert skews["40"].lift == pytest.approx(0.667, abs=1e-3)


def test_sparse_baseline_flagged_unreliable(conn):
    """기저가 거의 0 인 그룹은 리프트가 폭주한다. 신뢰 불가로 표시한다."""
    _rows(conn, "kw", {"2026-08-01": {"10": 30.0, "40": 70.0}})
    _rows(conn, "category:50000169", {"2026-08-01": {"10": 0.5, "40": 99.5}})
    skews = {s.group: s for s in dg.profile(conn, "kw", "50000169")}
    assert not skews["10"].reliable
    assert skews["40"].reliable
    # 신뢰 불가 그룹은 최대 쏠림 계산에서 빠진다
    assert dg.concentration(dg.profile(conn, "kw", "50000169")) == skews["40"].lift


def test_no_data_returns_empty(conn):
    assert dg.profile(conn, "없는키워드", "50000169") == []


def test_cross_cells_excluded_from_marginals(conn):
    """교차셀이 주변분포 계산에 섞이면 같은 클릭이 이중 계상된다.

    entity 한 컬럼에 전체·주변분포·교차셀이 모두 들어가므로 접두사 매칭이
    정밀하지 않으면 'gender=m' 을 고르려다 'gender=m;ages=20' 까지 잡는다.
    """
    recs = []
    for entity, value in (("gender=m", 60.0), ("gender=f", 40.0),
                          ("gender=m;ages=20", 25.0)):
        recs.append(RawRecord(
            channel="naver_shopping", keyword_raw="kw", entity=entity,
            metric_type="click_index", metric_value=value,
            observed_at="2026-08-01"))
    storage.insert_raw(conn, recs)

    shares = dg.daily_shares(conn, "kw", "gender")
    assert set(shares) == {"m", "f"}
    assert shares["m"] == pytest.approx(0.6)
    assert shares["f"] == pytest.approx(0.4)
