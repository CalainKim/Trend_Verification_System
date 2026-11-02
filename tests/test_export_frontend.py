"""화면 연동 데이터가 Trend Monitor 의 계약을 지키는지 본다."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from export_frontend import (  # noqa: E402
    build_ledger, build_type_skip, pick_weeks, self_attribute, type_of,
)


def _item(name, rank):
    return {"name": name, "rank": rank, "brand": "b", "price": 1000,
            "gender": "남", "is_new": False, "sale_percent": 0}


class TestTypeOf:
    """유형 분류는 순서가 의미를 가진다. 화면의 TYPE_RULES 와 같아야 한다."""

    def test_first_rule_wins(self):
        # 후드이면서 니트인 상품은 후드로 간다. 규칙 순서가 후드가 먼저다.
        assert type_of("MELLOW KNITTED HOOD_2COLOR") == "후드"
        assert type_of("RELAX HOODED KNIT [ BROWN ]") == "후드"

    def test_english_and_korean(self):
        assert type_of("Vintage Long Sleeve Henley Shirt Navy") == "롱슬리브"
        assert type_of("[스페셜오더] SWEAT SHIRT (5 COLOR)") == "맨투맨"
        assert type_of("Heavyweight Waffle Cotton Underwear Black") == "이너웨어"

    def test_unmatched_is_etc(self):
        assert type_of("알 수 없는 상품") == "기타"


class TestTypeSkip:
    def test_self_referential_attributes(self):
        # 사전 74종 가운데 이름이 곧 유형인 7개만 걸려야 한다.
        for canon in ("긴팔", "니트", "티셔츠", "후드티", "맨투맨", "블라우스", "탑"):
            assert self_attribute(canon), canon
        for canon in ("셔츠", "반팔", "와플", "크루넥", "울", "빈티지", "가디건"):
            assert not self_attribute(canon), canon

    def test_built_from_dictionary(self):
        import extract_attributes as ea

        attrs, _stop, _colors = ea.load_dictionary()
        skip = build_type_skip(attrs)
        # 화면 원본이 막던 셋은 반드시 들어 있어야 한다.
        assert skip["후드"] == ["후드티"]
        assert skip["니트"] == ["니트"]
        assert skip["탑"] == ["탑"]
        # 원본이 놓쳤던 넷도 채워져야 한다.
        assert skip["티셔츠"] == ["티셔츠"]
        assert skip["맨투맨"] == ["맨투맨"]
        assert skip["블라우스"] == ["블라우스"]
        assert skip["롱슬리브"] == ["긴팔"]


class TestLedger:
    """남음 판정은 (기준 - 확인) / (기준 - 감지) >= 0.5 다.

    아래 셋은 화면에 들어 있던 값에서 역산해 확인한 사례다. 판정식을 고치면
    여기서 먼저 깨진다.
    """

    @pytest.mark.parametrize("base, detect, hold, kept", [
        (41, 19, 30, True),    # 상승 22계단, 유지분 11, 11/22 = 0.50 으로 경계값
        (46, 18, 9, True),     # 확인 시점에 더 올랐다
        (27, 15, 32, False),   # 기준보다도 내려갔다
        (90, 65, 84, False),   # TOP100 안이지만 상승분을 거의 잃었다
    ])
    def test_keep_ratio(self, base, detect, hold, kept):
        got = build_ledger({"x": _item("상품", base)},
                           {"x": _item("상품", detect)},
                           {"x": _item("상품", hold)})
        assert got == [["상품", base, detect, hold, kept]]

    def test_dropped_out_of_top100(self):
        # 확인 시점에 목록 밖으로 나가면 순위를 null 로 두고 이탈로 본다.
        got = build_ledger({"x": _item("상품", 60)}, {"x": _item("상품", 6)}, {})
        assert got == [["상품", 60, 6, None, False]]

    def test_small_rise_is_not_a_case(self):
        # 10계단 미만은 감지 대상이 아니다.
        got = build_ledger({"x": _item("상품", 20)},
                           {"x": _item("상품", 12)},
                           {"x": _item("상품", 11)})
        assert got == []

    def test_absent_at_base_is_not_a_case(self):
        # 기준 시점에 없던 상품은 상승폭을 잴 수 없다.
        got = build_ledger({}, {"x": _item("상품", 5)}, {"x": _item("상품", 5)})
        assert got == []


class TestPickWeeks:
    def test_nearest_day_when_gap_is_missing(self):
        # 29CM 수집이 하루 빠진 주가 있다. 정확히 7일 전이 없으면 가장 가까운
        # 수집일로 당긴다.
        days = ["2026-10-17", "2026-10-25", "2026-11-01"]
        assert pick_weeks(days, "2026-11-01") == ["2026-10-17", "2026-10-25", "2026-11-01"]

    def test_rejects_day_without_collection(self):
        with pytest.raises(SystemExit):
            pick_weeks(["2026-11-01"], "2026-10-31")

    def test_rejects_when_history_is_too_short(self):
        with pytest.raises(SystemExit):
            pick_weeks(["2026-11-01"], "2026-11-01")
