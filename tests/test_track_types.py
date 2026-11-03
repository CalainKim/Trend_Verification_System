"""유형 다주 추적이 수준과 방향을 구분하는지 본다."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from track_types import (  # noqa: E402
    CAND, FLAT, GROW, NONE, SHRINK, SOLO, WATCH, direction, verdict,
    weekly_chain,
)


def _p(brand):
    return {"brand": brand}


class TestVerdict:
    """화면과 같은 판정식을 써야 한다. 다르면 같은 유형을 두고 화면과 보고서가
    다른 말을 한다."""

    def test_no_rise_is_no_signal(self):
        assert verdict([]) == NONE

    def test_three_products_three_brands_is_candidate(self):
        assert verdict([_p("a"), _p("b"), _p("c")]) == CAND

    def test_one_brand_dominating_is_brand_only(self):
        # 세 건이 올랐어도 둘이 같은 브랜드면 점유가 절반을 넘는다.
        assert verdict([_p("a"), _p("a"), _p("b")]) == SOLO

    def test_two_products_two_brands_is_watch(self):
        # 건수가 모자라 후보는 아니고, 점유가 절반이라 단독도 아니다.
        assert verdict([_p("a"), _p("b")]) == WATCH

    def test_boundary_share_is_not_brand_only(self):
        # 정확히 절반이면 단독으로 보지 않는다. 화면이 share > 0.5 를 쓴다.
        assert verdict([_p("a"), _p("a"), _p("b"), _p("b")]) != SOLO


class TestDirection:
    """방향은 TOP100 안 상품 수로 잰다.

    오른 상품 수를 TOP100 개수로 나누면 안 된다. 후드는 여덟에서 스물여덟으로
    늘면서 오른 수도 같이 늘어 비율이 제자리가 된다. 그 실수를 여기서 막는다.
    """

    def test_growing_presence(self):
        d, change = direction([8, 8, 10, 20, 28])
        assert d == GROW and change > 1.0

    def test_flat_big_category(self):
        # 티셔츠처럼 원래 크고 들쭉날쭉한 유형은 확대가 아니다.
        d, _ = direction([51, 66, 68, 53, 54])
        assert d == FLAT

    def test_shrinking(self):
        d, change = direction([59, 52, 37, 45, 36])
        assert d == SHRINK and change < 0

    def test_too_few_weeks_is_flat(self):
        # 세 주로는 앞뒤 절반을 나눌 수 없다. 모른다고 해야 한다.
        assert direction([1, 5, 20]) == (FLAT, 0.0)

    def test_from_zero_counts_as_growth(self):
        assert direction([0, 0, 3, 5])[0] == GROW


class TestWeeklyChain:
    def test_empty_collection_has_no_weeks(self):
        assert weekly_chain([], weeks=3) == []

    def test_picks_nearest_collection_day(self):
        days = ["2026-10-04", "2026-10-12", "2026-10-19", "2026-10-26"]
        got = weekly_chain(days, weeks=3)
        assert got == days

    def test_stops_at_a_real_gap(self):
        # 29CM 수집이 11일 빠진 구간이 있다. 억지로 이으면 2주 간격을 1주로
        # 읽어 궤적이 거짓말을 한다.
        days = ["2026-09-06", "2026-09-27", "2026-10-04"]
        got = weekly_chain(days, weeks=3)
        assert got == ["2026-09-27", "2026-10-04"]

    def test_respects_week_limit(self):
        days = [f"2026-09-{d:02d}" for d in (7, 14, 21, 28)]
        assert len(weekly_chain(days, weeks=2)) == 3
