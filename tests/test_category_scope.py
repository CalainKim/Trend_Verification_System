"""수집 범위는 넓히되 분석 범위는 그대로 두는 경계를 지킨다.

2026-11-04 부터 하의, 아우터, 신발도 모은다. 2차 화면이 "카테고리를 넘는
유행"을 말하려면 실제 자료가 있어야 하기 때문이다. 순위는 소급 조회가 안
되므로 먼저 켰다.

그런데 봉인한 문제지 139건과 기저율 59.7% 는 상의로 만들었고 검증 파트가
그 자료로 모델을 학습하고 있다. 읽는 쪽이 새로 들어온 행까지 가져가면
다음 빌드부터 기저율이 조용히 달라지고, 모델이 기준을 넘었다는 결론이
근거를 잃는다. 오류가 나지 않으므로 아무도 모른다.

그 경계가 살아 있는지를 자료를 섞어 가며 확인한다.
"""

from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trend_pipeline import persistence as ps, storage  # noqa: E402
from trend_pipeline.collectors.cm29_rank import (  # noqa: E402
    ALL_CATEGORY_CODES, EXTRA_CATEGORY_CODES, TOPS_CATEGORY_CODES,
)
from trend_pipeline.models import RawRecord  # noqa: E402

TOP = "272103100"        # 남성의류>상의. 분석 범위 안
BOTTOM = "272104100"     # 남성의류>하의. 분석 범위 밖


def rank_row(item: str, cat: str, day: str, rank: float) -> RawRecord:
    """순위 행. entity 에만 카테고리 꼬리가 붙는다."""
    return RawRecord(channel="commerce_rank", keyword_raw=f"{item} 상품",
                     metric_type="rank", metric_value=rank,
                     observed_at=f"{day}T22:00:00+09:00",
                     entity=f"{item}@{cat}",
                     metadata={"brand_kor": "브랜드"})


def side_row(item: str, day: str, kind: str, value: float) -> RawRecord:
    """리뷰와 하트 행. 수집기가 카테고리 꼬리를 붙이지 않는다."""
    return RawRecord(channel="commerce_rank", keyword_raw=f"{item} 상품",
                     metric_type=kind, metric_value=value,
                     observed_at=f"{day}T22:00:00+09:00", entity=item)


class TestScopeConstants(unittest.TestCase):
    def test_분석_범위는_수집기의_상의와_같다(self):
        # 두 곳에 같은 코드를 적어 두었다. 한쪽만 고치면 어느 날 조용히
        # 어긋나므로 여기서 묶어 둔다.
        self.assertEqual(set(ps.ANALYSIS_CATEGORY_CODES),
                         set(TOPS_CATEGORY_CODES))

    def test_추가_범위는_상의와_겹치지_않는다(self):
        self.assertFalse(set(EXTRA_CATEGORY_CODES) & set(TOPS_CATEGORY_CODES))

    def test_전체_범위는_둘을_합한_것이다(self):
        self.assertEqual(set(ALL_CATEGORY_CODES),
                         set(TOPS_CATEGORY_CODES) | set(EXTRA_CATEGORY_CODES))

    def test_수집이_분석보다_넓다(self):
        self.assertGreater(len(ALL_CATEGORY_CODES),
                           len(ps.ANALYSIS_CATEGORY_CODES))


class TestLoadSeriesScope(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        storage.init_db(self.conn)
        rows = []
        for i, day in enumerate(("2026-11-01", "2026-11-02")):
            rows += [rank_row("29cm:100", TOP, day, 10 + i),
                     side_row("29cm:100", day, "review_count", 50.0 + i),
                     side_row("29cm:100", day, "heart_count", 5.0 + i),
                     rank_row("29cm:900", BOTTOM, day, 3 + i),
                     side_row("29cm:900", day, "review_count", 80.0 + i)]
        storage.insert_raw(self.conn, rows)

    def tearDown(self):
        self.conn.close()

    def test_기본은_상의만_본다(self):
        s = ps.load_series(self.conn)
        self.assertEqual(set(s), {"29cm:100"})

    def test_하의가_들어와도_상의_값이_그대로다(self):
        # 경계의 핵심이다. 하의를 더 넣어도 상의 쪽 숫자가 한 톨도 안 움직여야
        # 한다. 움직이면 기저율이 달라진다.
        before = ps.load_series(self.conn)
        storage.insert_raw(self.conn, [
            rank_row("29cm:901", BOTTOM, "2026-11-01", 1.0),
            rank_row("29cm:902", BOTTOM, "2026-11-02", 2.0),
            side_row("29cm:901", "2026-11-01", "review_count", 999.0)])
        self.assertEqual(ps.load_series(self.conn), before)

    def test_상의_상품의_리뷰와_하트는_살아남는다(self):
        # 그 두 행은 entity 에 카테고리 꼬리가 없다. 꼬리로 바로 거르면
        # 통째로 빠지고, 그러면 리뷰 증가를 쓰는 특징이 전부 죽는다.
        s = ps.load_series(self.conn)["29cm:100"]["2026-11-01"]
        self.assertEqual(s["rank"], 10.0)
        self.assertEqual(s["review_count"], 50.0)
        self.assertEqual(s["heart_count"], 5.0)

    def test_하의_상품의_리뷰는_새어_들어오지_않는다(self):
        self.assertNotIn("29cm:900", ps.load_series(self.conn))

    def test_빈_튜플을_주면_전부_본다(self):
        s = ps.load_series(self.conn, categories=())
        self.assertEqual(set(s), {"29cm:100", "29cm:900"})

    def test_범위를_직접_주면_그것만_본다(self):
        s = ps.load_series(self.conn, categories=(BOTTOM,))
        self.assertEqual(set(s), {"29cm:900"})


if __name__ == "__main__":
    unittest.main()
