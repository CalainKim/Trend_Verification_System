"""상품명 속성 추출 검증.

사전을 손으로 고치는 파일이라 회귀가 조용히 생긴다. 표기 변형 하나를
지우면 그 속성이 집계에서 사라지는데 오류는 나지 않는다. 과거에 실제로
막혔던 지점을 사례로 남긴다.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import extract_attributes as ea  # noqa: E402


@pytest.fixture(scope="module")
def dic():
    attrs, stop, colors = ea.load_dictionary()
    return attrs, stop, colors


def found(name, dic):
    attrs, _, colors = dic
    return {h["canonical"] for h in ea.extract(name, attrs, colors)}


def test_half_zip_is_not_half_sleeve(dic):
    """half 하나로는 판단할 수 없다. 구 단위로 봐야 한다."""
    got = found("T.N.T. Classic HDP Half Zip Sweatshirt Heather Grey", dic)
    assert "하프집업" in got
    assert "반팔" not in got


def test_half_sleeve_is_short_sleeve(dic):
    assert "반팔" in found("BEING Nature Half Sleeve Blue", dic)


def test_korean_compound_keeps_attribute(dic):
    """롱슬리브티는 뒤에 티가 붙어도 긴팔이다."""
    assert "긴팔" in found("TG1-TS09 마일드 롱슬리브티 - [다크차콜]", dic)


def test_korean_spacing_variants(dic):
    """붙여 쓴 것과 띄어 쓴 것이 같게 잡혀야 한다."""
    assert "긴팔" in found("라글런 롱슬리브 티셔츠", dic)
    assert "긴팔" in found("보트넥 롱 슬리브 티셔츠", dic)


def test_english_plural(dic):
    """long sleeves 를 따로 적지 않아도 잡힌다."""
    assert "긴팔" in found("TOUGH LONG SLEEVES [Black Night]", dic)


def test_vintage_before_color_is_not_a_finish(dic):
    """Vintage Black 은 가공이 아니라 색상 수식어다."""
    assert "빈티지" not in found("9oz USA Cotton Tubular Tee Vintage Black", dic)


def test_distressed_is_a_finish(dic):
    assert "빈티지" in found("DISTRESSED BASEBALL L/S SHIRTS d.brown", dic)


def test_hangul_left_boundary(dic):
    """울(wool)이 서울에 걸리면 안 된다."""
    assert "울" not in found("서울 기념 티셔츠", dic)
    assert "울" in found("Hale Wool Hoodie Knit (Pink)", dic)


def test_hyphen_in_match(dic):
    assert "모크넥" in found("Wool Tencel Mock-Neck T-Shirt_Charcoal", dic)


def test_longest_variant_wins(dic):
    """halter 가 먼저 걸리면 halter neck 을 놓친다."""
    assert "홀터넥" in found("Halter Neck Button Top_2Color", dic)


def test_clean_strips_bracket_prefix_and_batch():
    out = ea.clean("[3차 재입고] 로우엣지 래글런 롱슬리브 티셔츠_차콜")
    assert "3차" not in out and "재입고" not in out
    assert "래글런" in out


def test_leftover_removes_hyphenated_match(dic):
    """붙임표가 섞인 매칭도 꼬리에서 지워져야 한다."""
    attrs, stop, colors = dic
    name = "Wool Tencel Mock-Neck T-Shirt_Charcoal"
    hits = ea.extract(name, attrs, colors)
    tail = ea.leftover_tokens(name, hits, stop)
    assert "neck" not in tail and "mock" not in tail
