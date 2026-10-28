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
