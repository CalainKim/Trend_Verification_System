"""규칙 점수가 자료 없음을 나쁜 신호로 바꾸지 않는지 본다.

이 점수는 채점에서 기저율을 넘지 못했다. 어느 문턱에서도 그랬다. 그래도
테스트를 두는 이유는, 나중에 가중치를 손볼 때 여기 적힌 성질이 깨지면
숫자가 왜 움직였는지 알 수 없게 되기 때문이다.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from score_rule import W, product_score, season_of  # noqa: E402


class TestMissingData:
    """없는 값은 가운데(50)로 둔다.

    0 으로 두면 자료가 없는 것이 나쁜 신호가 된다. 수집이 안 된 상품과
    실제로 나쁜 상품은 다르다.
    """

    def test_all_missing_is_neutral(self):
        got = product_score({}, None)
        assert got["score"] == 50
        assert set(got["parts"].values()) == {50}

    def test_one_missing_does_not_drag(self):
        full = product_score({"rank_rise": 40.0, "review_delta": 20.0,
                              "sale_percent_delta": 0.0}, 1.5)
        # 리뷰만 빠져도 나머지 점수는 그대로여야 한다
        part = product_score({"rank_rise": 40.0, "sale_percent_delta": 0.0}, 1.5)
        assert part["parts"]["rise"] == full["parts"]["rise"]
        assert part["parts"]["season"] == full["parts"]["season"]
        assert part["parts"]["review"] == 50


class TestParts:
    def test_rise_scales_from_detection_threshold(self):
        # 10계단이 감지 문턱이라 거기서 0점, 40계단에서 만점이다
        assert product_score({"rank_rise": 10.0}, None)["parts"]["rise"] == 0
        assert product_score({"rank_rise": 40.0}, None)["parts"]["rise"] == 100

    def test_discount_increase_is_penalised(self):
        up = product_score({"sale_percent_delta": 20.0}, None)["parts"]["discount"]
        flat = product_score({"sale_percent_delta": 0.0}, None)["parts"]["discount"]
        down = product_score({"sale_percent_delta": -20.0}, None)["parts"]["discount"]
        assert up < flat < down

    def test_seasonal_move_scores_zero(self):
        # 작년과 같은 배수면 계절성이지 올해만의 신호가 아니다
        assert product_score({}, 1.0)["parts"]["season"] == 0
        assert product_score({}, 1.5)["parts"]["season"] == 100

    def test_weights_sum_to_one(self):
        assert abs(sum(W.values()) - 1.0) < 1e-9


class TestSeasonOf:
    def test_reads_ratio_from_evidence(self):
        case = {"evidence": [
            {"id": "rank_change", "observation": "순위가 올랐다"},
            {"id": "seasonality", "observation": "작년 같은 시기 대비 1.37 배다."},
        ]}
        assert season_of(case) == 1.37

    def test_none_when_not_measured(self):
        case = {"evidence": [
            {"id": "seasonality", "observation": "작년 관측이 없어 재지 못했다"},
        ]}
        assert season_of(case) is None

    def test_none_when_absent(self):
        assert season_of({"evidence": []}) is None
