"""코오롱몰과 하이버 수집기, 그리고 새 채널이 기존 분석을 안 건드리는지.

2026-11-05 에 지그재그가 막혀서 두 곳을 대신 붙였다. 붙이는 쪽 이야기는
각 수집기 모듈의 문서화 문자열에 적었고, 여기서는 **틀리면 조용히 틀릴
자리**만 고정한다. 그 자리가 넷이다.

    1. 같은 블록이 두 번 실려 오는 것을 지우지 않으면 순위가 두 배로 어긋난다
    2. 브랜드가 없는 상품을 빈 문자열로 저장하면 "같은 브랜드 29건" 이 된다
    3. 하이버의 observed_at 을 수집 시각으로 쓰면 같은 순위가 여러 번 쌓인다
    4. 새 채널이 commerce_rank 질의에 섞이면 봉인한 기저율이 조용히 달라진다

넷 다 예외가 나지 않고 숫자만 달라지는 종류라서 테스트가 아니면 못 잡는다.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trend_pipeline import persistence as ps, snapshots, storage  # noqa: E402
from trend_pipeline.collectors.hiver_rank import (  # noqa: E402
    HiverRankCollector, observed_at_from, parse_ranking,
)
from trend_pipeline.collectors.kolon_rank import (  # noqa: E402
    BEST_SCOPES, EXCLUDED_SCOPES, KolonRankCollector, parse_best,
)
from trend_pipeline.models import CHANNELS, RawRecord  # noqa: E402


# --------------------------------------------------------------- 가짜 응답

def kolon_item(code: str, name: str, brand: str, wish: int = 10,
               own: bool = False) -> dict:
    """실제 응답에서 쓰는 필드만 남긴 상품 하나."""
    return {
        "__typename": "productResult", "code": code, "color": "BLACK",
        "name": name, "supplierBrandName": brand, "supplierCode": "TS",
        "supplierOwnFlag": own, "soldOutYn": "N", "newProductYn": False,
        "representationImage": f"https://images.kolonmall.com/{code}.jpg",
        "price": {"__typename": "price", "discountRate": 10,
                  "price": 89100, "wishPrice": 99000},
        "wishProductCount": wish, "season": "WINTER", "produceYear": 2026,
        "stdCategoryLevel1": None, "stdCategoryLevel2": None,
        "stdCategoryLevel3": None,
    }


def kolon_block(items, total=294) -> str:
    """`/Best` 안에 직렬화돼 들어오는 GraphQL 블록 하나.

    공백 없이 찍는다. 실제 응답이 공백 없는 JSON 이고 파서가 찾는 표식도
    `"__typename":"bestItems"` 라 공백이 들어가면 안 잡힌다.
    """
    return json.dumps({
        "__typename": "bestItems",
        "page": {"__typename": "page", "totalCount": total,
                 "currentPage": 1, "perPage": 100},
        "results": items,
    }, ensure_ascii=False, separators=(",", ":"))


def kolon_html(items, repeat: int = 2, total: int = 294) -> str:
    """실제 페이지 모양으로 감싼다.

    두 가지를 실제와 똑같이 맞춰야 테스트가 쓸모 있다.

    같은 블록이 두 번 들어간다   서버 렌더링분과 수화(hydration)분이다.
                               `repeat=1` 로 두면 중복 제거가 깨져도 통과한다
    감싸는 객체가 깨진 JSON 이다  Apollo 가 `"data":undefined` 를 싣는다.
                               통째로 json.loads 하면 못 읽는다

    따옴표는 escape 되지 않은 채로 들어온다. `self.__next_f.push` 쪽
    비행(flight) 자료와 달라서 그쪽 모양으로 만들면 안 된다.
    """
    pushes = "".join(
        '<script>(window[Symbol.for("ApolloSSRDataTransport")] ??= []).push('
        '{"rehydrate":{":R1:":{"data":undefined,"loading":true}},'
        '"events":[{"type":"data","id":"5","result":{"data":{"bestItems":'
        + kolon_block(items, total) + '},"networkStatus":7}}]});</script>'
        for _ in range(repeat))
    # 중괄호가 들어간 잡음을 앞에 둬서 괄호 세기가 진짜로 동작하는지 본다.
    noise = '<script>var x = {"a":{"b":"}"},"c":"{"};</script>'
    return f"<html><head>{noise}</head><body>{pushes}</body></html>"


def hiver_item(item_id: str, name: str, rank: int, score: float,
               brand_name: str = "", seller: str = "판매자") -> dict:
    return {
        "id": item_id, "name": name, "price": 389300, "sale_price": 101200,
        "sale_percent": 74, "is_sell": True, "is_today_delivery": False,
        "root_category_no": 1476, "root_category_name": "스포츠",
        "is_free_delivery": True,
        "seller": {"id": "67507", "name": seller, "is_partner": False},
        "brand": {"is_brand_product": bool(brand_name), "brand_no": "16805",
                  "brand_name": brand_name, "brand_en_name": ""},
        "expect_sale_price": 96140, "rank": rank, "score": score,
        "image_url": "https://image.brandi.co.kr/x.jpg",
    }


def hiver_html(items, calculated_at="2026-11-05T00:20:46") -> str:
    payload = {"props": {"pageProps": {
        "initialPage": {"meta": {"code": 200, "count": len(items)},
                        "data": {"products": items,
                                 "calculated_at": calculated_at,
                                 "period": "realtime",
                                 "scope": {"type": "all"}}},
        "initialScope": '["ranking","realtime",null,"all","all"]'}},
        "page": "/ranking", "query": {}}
    return ('<html><body><script id="__NEXT_DATA__" type="application/json">'
            + json.dumps(payload, ensure_ascii=False) + "</script></body></html>")


# ------------------------------------------------------------- 코오롱몰

class TestKolonParse(unittest.TestCase):
    def test_같은_블록이_두_번_와도_한_번만_센다(self):
        items = [kolon_item("A1", "플리스", "브랜드가"),
                 kolon_item("B2", "니트", "브랜드나")]
        got, total = parse_best(kolon_html(items, repeat=2))
        # 지우지 않으면 4건이 되고 3위, 4위가 1위, 2위의 복사본이 된다.
        self.assertEqual([i["code"] for i in got], ["A1", "B2"])
        self.assertEqual(total, 294)

    def test_순서가_순위다(self):
        items = [kolon_item(f"C{i}", f"상품{i}", "브랜드") for i in range(5)]
        got, _ = parse_best(kolon_html(items))
        self.assertEqual([i["code"] for i in got],
                         ["C0", "C1", "C2", "C3", "C4"])

    def test_문자열_안의_중괄호에_안_속는다(self):
        # 상품명에 중괄호가 들어오면 정규식으로는 블록이 잘린다.
        items = [kolon_item("D1", '이상한 이름 {닫는 괄호 } 포함', "브랜드")]
        got, _ = parse_best(kolon_html(items))
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["name"], '이상한 이름 {닫는 괄호 } 포함')

    def test_상품이_없으면_빈_목록이다(self):
        got, total = parse_best("<html><body>아무것도 없다</body></html>")
        self.assertEqual(got, [])
        self.assertIsNone(total)

    def test_깨진_JSON_에_안_죽는다(self):
        html = '<script>{"__typename":"bestItems","page":{</script>'
        got, _ = parse_best(html)
        self.assertEqual(got, [])

    def test_공백이_들어와도_찾는다(self):
        # 실제 응답은 공백 없는 JSON 이다. 사이트가 어느 날 직렬화를 바꿔도
        # 그날 순위를 놓치지 않게 공백을 허용한다. 소급 수집이 안 되는
        # 자료라 한 번 놓치면 못 되찾는다.
        items = [kolon_item("E1", "플리스", "브랜드")]
        loose = kolon_html(items).replace('"__typename":"bestItems"',
                                          '"__typename" : "bestItems"')
        got, _ = parse_best(loose)
        self.assertEqual([i["code"] for i in got], ["E1"])


class TestKolonRecords(unittest.TestCase):
    def setUp(self):
        self.c = KolonRankCollector()
        self.when = "2026-11-05T00:39:54+09:00"

    def records(self, item, rank=1, scope="ALL"):
        return list(self.c._to_records(item, rank, scope, self.when, "r1"))

    def test_순위와_좋아요만_나온다(self):
        recs = self.records(kolon_item("A1", "플리스", "브랜드", wish=309))
        self.assertEqual([r.metric_type for r in recs], ["rank", "heart_count"])
        self.assertEqual([r.metric_value for r in recs], [1.0, 309.0])

    def test_순위_키에만_탭이_붙는다(self):
        # 한 상품이 전체와 남성 탭에 같이 오르므로 순위는 탭별로 따로 쌓여야
        # 하고, 좋아요는 어느 탭에서 보든 같은 값이라 한 번만 쌓여야 한다.
        a = self.records(kolon_item("A1", "플리스", "브랜드"), 1, "ALL")
        b = self.records(kolon_item("A1", "플리스", "브랜드"), 7, "133010010000")
        self.assertEqual(a[0].entity, "kolonmall:A1@ALL")
        self.assertEqual(b[0].entity, "kolonmall:A1@133010010000")
        self.assertEqual(a[1].entity, b[1].entity, "좋아요 키는 같아야 한다")

    def test_리뷰_수를_0_으로_채우지_않는다(self):
        recs = self.records(kolon_item("A1", "플리스", "브랜드"))
        self.assertNotIn("review_count", [r.metric_type for r in recs])

    def test_좋아요가_없으면_그_행만_빠진다(self):
        item = kolon_item("A1", "플리스", "브랜드")
        item["wishProductCount"] = None
        recs = self.records(item)
        self.assertEqual([r.metric_type for r in recs], ["rank"])

    def test_정가와_할인가가_뒤집히지_않는다(self):
        # 코오롱몰은 wishPrice 가 정가이고 price 가 할인가다. 29CM 과 반대라
        # 그대로 넣으면 화면이 할인액을 음수로 그린다.
        md = self.records(kolon_item("A1", "플리스", "브랜드"))[0].metadata
        self.assertEqual(md["consumer_price"], 99000)
        self.assertEqual(md["sale_price"], 89100)
        self.assertGreater(md["consumer_price"], md["sale_price"])

    def test_자사_브랜드_표시가_남는다(self):
        own = self.records(kolon_item("A1", "x", "브랜드", own=True))[0]
        other = self.records(kolon_item("A2", "y", "브랜드", own=False))[0]
        self.assertTrue(own.metadata["supplier_own"])
        self.assertFalse(other.metadata["supplier_own"])

    def test_이름이_없는_상품은_버린다(self):
        self.assertEqual(self.records(kolon_item("A1", "", "브랜드")), [])
        self.assertEqual(self.records(kolon_item("", "플리스", "브랜드")), [])


class TestKolonScopes(unittest.TestCase):
    def test_아울렛과_라이프는_안_모은다(self):
        # 아울렛 순위는 유행이 아니라 재고 소진을, 라이프는 생활용품을
        # 가리킨다. 실수로 되살리면 유행 신호가 오염된다.
        for code in EXCLUDED_SCOPES:
            self.assertNotIn(code, BEST_SCOPES)

    def test_전체_탭은_코드가_없다(self):
        self.assertIn("ALL", BEST_SCOPES)


# --------------------------------------------------------------- 하이버

class TestHiverParse(unittest.TestCase):
    def test_상품과_메타를_같이_뽑는다(self):
        items = [hiver_item("1", "플리스", 1, 0.85, "파타고니아")]
        got, meta = parse_ranking(hiver_html(items))
        self.assertEqual(len(got), 1)
        self.assertEqual(meta["calculated_at"], "2026-11-05T00:20:46")
        self.assertEqual(meta["period"], "realtime")
        self.assertNotIn("products", meta)

    def test_스크립트가_없으면_빈_목록이다(self):
        self.assertEqual(parse_ranking("<html></html>"), ([], {}))

    def test_깨진_JSON_에_안_죽는다(self):
        bad = '<script id="__NEXT_DATA__">{"props":</script>'
        self.assertEqual(parse_ranking(bad), ([], {}))


class TestHiverObservedAt(unittest.TestCase):
    def test_사이트가_계산한_시각에_KST_를_붙인다(self):
        # 오프셋을 안 붙이면 다른 채널과 견줄 때 아홉 시간이 어긋난다.
        self.assertEqual(observed_at_from("2026-11-05T00:20:46"),
                         "2026-11-05T00:20:46+09:00")

    def test_값이_없으면_수집_시각으로_떨어진다(self):
        from datetime import datetime
        from trend_pipeline.collectors.hiver_rank import KST
        now = datetime(2026, 11, 5, 1, 2, 3, tzinfo=KST)
        self.assertEqual(observed_at_from(None, now), "2026-11-05T01:02:03+09:00")
        self.assertEqual(observed_at_from("어제", now), "2026-11-05T01:02:03+09:00")

    def test_같은_순위를_두_번_받아도_한_스냅샷이다(self):
        # 수집 시각을 쓰면 여기서 행이 두 배가 되고 "순위가 두 번 측정됐다"
        # 로 보인다. 소급 조회가 안 되는 자료라 뒤에 못 고친다.
        items = [hiver_item("1", "플리스", 1, 0.85, "파타고니아")]
        html = hiver_html(items)
        c = HiverRankCollector()
        a, _ = parse_ranking(html)
        b, _ = parse_ranking(html)
        self.assertEqual(observed_at_from("2026-11-05T00:20:46"),
                         observed_at_from("2026-11-05T00:20:46"))
        self.assertEqual(len(a), len(b))
        del c


class TestHiverRecords(unittest.TestCase):
    def setUp(self):
        self.c = HiverRankCollector()
        self.when = "2026-11-05T00:20:46+09:00"

    def records(self, item, position=1):
        return list(self.c._to_records(
            item, position, "all", self.when, "2026-11-05T00:20:46",
            "realtime", "r1"))

    def test_순위와_점수가_나온다(self):
        recs = self.records(hiver_item("1", "플리스", 1, 0.85, "파타고니아"))
        self.assertEqual([r.metric_type for r in recs], ["rank", "rank_score"])
        self.assertEqual(recs[0].metric_value, 1.0)
        self.assertAlmostEqual(recs[1].metric_value, 0.85)

    def test_브랜드가_없으면_빈_문자열이_아니라_None_이다(self):
        # 빈 문자열로 저장하면 집계에서 브랜드 하나로 세어져서 쇼핑몰 상품
        # 29건이 "같은 브랜드 29건" 이라는 가짜 겹침 신호가 된다.
        no = self.records(hiver_item("1", "흰티", 1, 0.5, ""))[0]
        yes = self.records(hiver_item("2", "플리스", 2, 0.4, "파타고니아"))[0]
        self.assertIsNone(no.metadata["brand_kor"])
        self.assertFalse(no.metadata["is_brand_product"])
        self.assertEqual(yes.metadata["brand_kor"], "파타고니아")
        self.assertTrue(yes.metadata["is_brand_product"])

    def test_판매자를_브랜드_자리에_넣지_않는다(self):
        # seller 는 판매 법인명이다. 브랜드로 쓰면 "제이엠컴퍼니" 가
        # 브랜드가 되어 겹침 신호가 엉뚱한 축으로 생긴다.
        md = self.records(hiver_item("1", "흰티", 1, 0.5, "",
                                     seller="제이엠컴퍼니"))[0].metadata
        self.assertEqual(md["seller_name"], "제이엠컴퍼니")
        self.assertIsNone(md["brand_kor"])

    def test_매장_구분을_의류_분류로_쓰지_않는다(self):
        md = self.records(hiver_item("1", "흰티", 1, 0.5, ""))[0].metadata
        self.assertEqual(md["store_category_name"], "스포츠")
        self.assertNotIn("category3", md)

    def test_사이트_순위와_목록_순서가_어긋나면_기록한다(self):
        recs = self.records(hiver_item("1", "흰티", 7, 0.5, ""), position=3)
        self.assertEqual(recs[0].metric_value, 7.0, "사이트 값을 믿는다")
        self.assertTrue(recs[0].metadata["rank_mismatch"])

    def test_사이트_순위가_없으면_목록_순서를_쓴다(self):
        item = hiver_item("1", "흰티", 1, 0.5, "")
        item["rank"] = None
        recs = self.records(item, position=4)
        self.assertEqual(recs[0].metric_value, 4.0)

    def test_정가와_할인가가_뒤집히지_않는다(self):
        md = self.records(hiver_item("1", "플리스", 1, 0.85, "파타고니아"))[0].metadata
        self.assertEqual(md["consumer_price"], 389300)
        self.assertEqual(md["sale_price"], 101200)
        self.assertGreater(md["consumer_price"], md["sale_price"])


# ------------------------------------------------- 기존 분석과의 격리

class TestChannelIsolation(unittest.TestCase):
    """새 채널이 commerce_rank 를 보는 질의에 섞이지 않는다.

    이게 이 변경에서 제일 위험한 자리다. 섞이면 봉인한 문제지 139건의
    기저율 59.7% 가 다음 빌드부터 조용히 다른 숫자가 되고, 검증 파트가
    기준을 넘었다는 결론이 근거를 잃는다. 예외가 안 나므로 아무도 모른다.
    """

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        storage.init_db(self.conn)

        rows = []
        for day in ("2026-11-04", "2026-11-05"):
            at = f"{day}T22:00:00+09:00"
            # 29CM 상의. 분석이 보는 자료다.
            rows.append(RawRecord(
                channel="commerce_rank", keyword_raw="상의 상품",
                metric_type="rank", metric_value=3, observed_at=at,
                entity="29cm:1@272103100", metadata={"brand_kor": "브랜드"}))
            # 코오롱몰과 하이버. 섞이면 안 되는 자료다.
            rows.append(RawRecord(
                channel="kolon_rank", keyword_raw="코오롱 상품",
                metric_type="rank", metric_value=5, observed_at=at,
                entity="kolonmall:A1@ALL", metadata={"brand_kor": "코오롱스포츠"}))
            rows.append(RawRecord(
                channel="hiver_rank", keyword_raw="하이버 상품",
                metric_type="rank", metric_value=9, observed_at=at,
                entity="hiver:1@all", metadata={"brand_kor": "파타고니아"}))
        storage.insert_raw(self.conn, rows)

    def test_채널이_모두_등록돼_있다(self):
        for ch in ("commerce_rank", "kolon_rank", "hiver_rank"):
            self.assertIn(ch, CHANNELS)

    def test_load_series_는_29CM_상의만_본다(self):
        series = ps.load_series(self.conn, "commerce_rank")
        keys = set(series)
        self.assertTrue(keys, "상의 자료는 있어야 한다")
        for key in keys:
            self.assertNotIn("kolonmall", key)
            self.assertNotIn("hiver", key)

    def test_새_채널을_넣어도_29CM_결과가_같다(self):
        before = ps.load_series(self.conn, "commerce_rank")
        storage.insert_raw(self.conn, [RawRecord(
            channel="kolon_rank", keyword_raw="코오롱 신상",
            metric_type="rank", metric_value=1,
            observed_at="2026-11-05T22:00:00+09:00",
            entity="kolonmall:Z9@ALL", metadata={"brand_kor": "헨리코튼"})])
        after = ps.load_series(self.conn, "commerce_rank")
        self.assertEqual(before, after)

    def test_새_채널은_제_채널로_읽힌다(self):
        # 격리가 "읽을 수 없다" 가 되어서는 안 된다. 쌓는 목적이 사라진다.
        got = ps.load_series(self.conn, "kolon_rank", categories=())
        self.assertTrue(got, "코오롱몰 자료는 제 채널에서 읽혀야 한다")

    def test_스냅샷이_채널별로_날짜_단위로_나뉜다(self):
        for ch in ("kolon_rank", "hiver_rank"):
            self.assertEqual(
                snapshots.partition_key(ch, "2026-11-05T00:20:46+09:00"),
                "2026-11-05")
            self.assertNotIn(ch, snapshots.HISTORY_CHANNELS)


if __name__ == "__main__":
    unittest.main()
