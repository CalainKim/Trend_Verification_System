"""하이버 실시간 랭킹 수집기 (세 번째 커머스 채널).

왜 하이버인가
------------
2026-11-05 에 지그재그가 막힌 것을 확인하고 대체 소스를 여덟 곳 봤다
(`docs/robots-compliance.md` 의 "재확인 2026-11-05"). 코오롱몰을 1순위로
붙이고 하이버를 2순위로 붙인다.

코오롱몰과 성격이 다르다는 것이 붙이는 이유다. 코오롱몰은 자사 브랜드가
순위의 절반이라 "브랜드가 밀어서 오른 것" 과 "사람들이 사서 오른 것" 이
섞인다. 하이버는 편집샵이라 그 교란이 다르게 들어간다. 두 교란이 같은
방향으로 틀릴 이유가 없으므로 둘이 같은 상품을 가리키면 근거가 세진다.

운영사는 브랜디다(이미지 호스트가 image.brandi.co.kr 이다). 그래서
브랜디를 나중에 붙이더라도 **하이버와 같은 채널로 묶어야 한다.** 29CM 와
무신사를 한 채널로 묶는 것과 같은 이유다.

받아지는 것과 안 받아지는 것
--------------------------
`/ranking` 한 경로뿐이다. `period`, `page`, `limit`, `scope` 를 쿼리로
넘겨 봤지만 전부 무시하고 같은 응답이 온다. 그래서 한 회차에 50건이다.
29CM 과 코오롱몰이 100건이라 셋 중 가장 얕다.

    얻는 것   순위, 순위 점수, 브랜드(일부), 판매자, 정가, 할인가
    없는 것   리뷰 수, 좋아요 수, 의류 카테고리

`root_category_name` 은 스포츠, 브랜드, 쇼핑몰이다. 매장 구분이고 의류
분류가 아니다. 상의와 하의를 가르려면 상품명으로 해야 한다.

브랜드 커버리지가 42% 다
----------------------
`brand.brand_name` 이 50건 중 21건에만 있다. 나머지 29건은
`is_brand_product` 가 false 인 쇼핑몰 상품이고 브랜드명이 빈 문자열로 온다.

빈 값을 상품명 첫 토큰으로 메우지 않는다. 상품명이

    [노마진] 아미 드 꾀흐 빅하트 시그니처 맨투맨 6종 택1
    [당일출고/1+1할인] 남자 코듀로이 골덴 바지 FC74 3color 빅

꼴이라 첫 토큰이 홍보 문구이거나 아예 브랜드가 아닌 경우가 많다. 추측해서
채우면 틀린 브랜드가 조용히 쌓이고, 브랜드 겹침 신호가 거짓으로 커진다.
없는 것은 None 으로 둔다. 커버리지 42% 는 집계할 때 분모로 쓴다.

`score` 를 같이 저장하는 이유
---------------------------
응답에 `score` 가 0.4335 에서 0.85 사이로 온다. 순위 점수 원값이다.

순위만 있으면 1위와 2위 사이가 얼마나 벌어졌는지 모른다. 1위가 압도적인
날과 1위부터 10위가 붙어 있는 날이 똑같이 "1위" 로 보인다. 점수가 있으면
그것이 구분된다. 29CM 과 코오롱몰에는 없는 지표라 하이버에서만 쓸 수
있지만, 없는 쪽에 맞춰 버리면 있는 정보를 버리는 것이다.

observed_at 을 우리 시각으로 쓰지 않는다
------------------------------------
응답에 `calculated_at` 이 온다. 사이트가 순위를 계산한 시각이다. 스키마
주석대로 `observed_at` 은 "지표가 실제로 가리키는 시점" 이므로 우리가 긁은
시각이 아니라 이 값을 쓴다.

부수 효과가 좋다. 순위가 아직 재계산되지 않았으면 두 번 받아도 같은
`observed_at` 이라 `INSERT OR IGNORE` 가 같은 스냅샷으로 알아본다.
재계산됐으면 다른 스냅샷이 된다. 즉 "몇 번 돌렸나" 가 아니라 "순위가 몇 번
바뀌었나" 가 쌓인다. 29CM 과 코오롱몰은 그 값을 안 주니 우리 시각을 쓸
수밖에 없었다.

robots 근거
----------
2026-11-05 확인 결과 `User-agent: *` 가 `/products/*`, `/store/*`,
`/search`, `/thevc`, `/favor`, `/authorization`, `/timeout`, `/api/`,
`/onelink`, `/onelinkrf`, `/reviews/*/edit`, `/products/*/inquiries`,
`/cooperation` 을 막는다. `/ranking` 은 목록에 없으므로 허용이다.

상품 상세(`/products/*`)와 API(`/api/`)는 막혀 있으니 쓰지 않는다. 순위
페이지가 서버 렌더링이라 그것만으로 충분하다.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterator, List, Optional, Tuple

import requests

from ..models import RawRecord
from .base import Collector

KST = timezone(timedelta(hours=9))

RANKING_URL = "https://www.hiver.co.kr/ranking"
#: 상품 상세는 robots 가 막는다. 수집하지 않고 사람이 눌러 볼 주소로만 적는다.
PRODUCT_URL = "https://www.hiver.co.kr/products/{item_id}"

#: 순위 목록 구분. `/ranking` 이 범위를 못 받으므로 지금은 하나뿐이다.
#: 순위 행 키에 들어가므로 나중에 범위가 늘어도 과거 키가 안 깨진다.
DEFAULT_SCOPE = "all"

DEFAULT_USER_AGENT = (
    "TrendSignalResearchBot/0.1 "
    "(Ajou Univ. self-directed project; non-commercial research)"
)

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)

#: 초 단위까지 있고 시간대가 없는 ISO 문자열. 한국 사이트라 KST 로 읽는다.
_NAIVE_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")


def parse_ranking(html: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """`/ranking` 응답에서 상품 목록과 메타를 뽑는다.

    자료가 `__NEXT_DATA__` 안에 그대로 들어 있다. 별도 API 요청이 필요
    없으므로 robots 가 막은 `/api/` 를 건드리지 않는다.

    돌려주는 메타는 `calculated_at`, `period`, `scope` 다. 상품이 없으면
    빈 목록이고, 부르는 쪽이 재시도를 판단한다.
    """
    m = _NEXT_DATA_RE.search(html)
    if not m:
        return [], {}
    try:
        payload = json.loads(m.group(1))
    except json.JSONDecodeError:
        return [], {}
    page = (((payload.get("props") or {}).get("pageProps") or {})
            .get("initialPage") or {})
    data = page.get("data") or {}
    products = data.get("products") or []
    meta = {k: v for k, v in data.items() if k != "products"}
    return products, meta


def observed_at_from(calculated_at: Optional[str],
                     now: Optional[datetime] = None) -> str:
    """`calculated_at` 을 `observed_at` 으로 바꾼다.

    사이트가 주는 값은 `2026-11-05T00:20:46` 처럼 시간대가 없다. 한국
    서비스라 KST 로 읽고 오프셋을 붙인다. 안 붙이면 나중에 다른 채널과
    시점을 견줄 때 아홉 시간이 어긋난다.

    값이 없거나 모양이 다르면 수집 시각으로 떨어진다. 그 자리에서 죽이면
    그날 순위를 영영 못 받는다. 떨어졌다는 것은 metadata 에 적어 둔다.
    """
    if calculated_at and _NAIVE_ISO_RE.match(calculated_at):
        return datetime.fromisoformat(calculated_at).replace(
            tzinfo=KST).isoformat()
    now = now or datetime.now(KST)
    return now.astimezone(KST).replace(microsecond=0).isoformat()


class HiverRankCollector(Collector):
    """하이버 판매 순위를 받아 오는 수집기다."""
    channel = "hiver_rank"
    platform = "hiver"

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        min_interval_sec: float = 2.0,
        timeout_sec: float = 30.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        super().__init__()
        self.min_interval_sec = min_interval_sec
        self.timeout_sec = timeout_sec
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ko-KR,ko;q=0.9",
            "Referer": "https://www.hiver.co.kr/",
        })

    # ------------------------------------------------------------------ HTTP

    def fetch_ranking(self, tries: int = 3
                      ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """순위 한 회차를 받는다.

        순위는 소급 조회가 안 된다. 한 번 실패했다고 버리면 그 회차는 영영
        못 되찾으므로 쉬었다 다시 묻고, 그래도 안 되면 무엇이 왔는지 적고
        멈춘다. 조용히 빈 목록을 돌려주면 "순위가 없었다" 와 구분이 안 된다.
        """
        last = ""
        for attempt in range(tries):
            self.sleep()
            resp = self.session.get(RANKING_URL, timeout=self.timeout_sec)
            resp.raise_for_status()
            products, meta = parse_ranking(resp.text)
            if products:
                return products, meta
            last = (f"HTTP {resp.status_code}, {len(resp.text)}자, "
                    f"__NEXT_DATA__ {'있음' if _NEXT_DATA_RE.search(resp.text) else '없음'}")
            if attempt < tries - 1:
                time.sleep(2.0 * (attempt + 1))
        raise RuntimeError(f"하이버 순위에서 상품을 못 뽑았다: {last}")

    # --------------------------------------------------------------- 수집

    def collect(
        self,
        run_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> Iterator[RawRecord]:
        """하이버 순위 페이지를 한 번 받아 상품마다 기록을 만든다."""
        products, meta = self.fetch_ranking()
        calculated_at = meta.get("calculated_at")
        observed_at = observed_at_from(calculated_at, now)
        scope = ((meta.get("scope") or {}).get("type")) or DEFAULT_SCOPE

        for position, item in enumerate(products, start=1):
            yield from self._to_records(
                item, position, scope, observed_at, calculated_at,
                meta.get("period"), run_id)

    def _to_records(
        self,
        item: Dict[str, Any],
        position: int,
        scope: str,
        observed_at: str,
        calculated_at: Optional[str],
        period: Optional[str],
        run_id: Optional[str],
    ) -> Iterator[RawRecord]:
        """하이버 응답의 상품 하나를 순위 기록으로 바꾼다."""
        item_id = item.get("id")
        name = (item.get("name") or "").strip()
        if not item_id or not name:
            return

        brand = item.get("brand") or {}
        seller = item.get("seller") or {}
        # 빈 문자열은 "브랜드 없는 쇼핑몰 상품" 이다. 빈 문자열로 저장하면
        # 집계에서 브랜드 하나로 세어져서 "같은 브랜드 29건" 이 된다.
        brand_name = (brand.get("brand_name") or "").strip() or None

        # 사이트가 주는 rank 가 목록 순서와 어긋나면 사이트 값을 믿는다.
        # 다만 어긋났다는 사실은 남긴다. 조용히 덮으면 나중에 순위가 왜
        # 건너뛰는지 알 수 없다.
        site_rank = item.get("rank")
        rank = site_rank if isinstance(site_rank, int) and site_rank > 0 else position

        metadata = {
            "platform": self.platform,
            "item_id": str(item_id),
            "brand_kor": brand_name,
            "brand_eng": (brand.get("brand_en_name") or "").strip() or None,
            "brand_no": brand.get("brand_no"),
            "is_brand_product": bool(brand.get("is_brand_product")),
            "seller_name": seller.get("name"),
            "seller_id": seller.get("id"),
            "seller_is_partner": bool(seller.get("is_partner")),
            "sold_out": not bool(item.get("is_sell", True)),
            # price 가 정가이고 sale_price 가 할인가다. 29CM 과 코오롱몰에
            # 맞춰 이름을 바꿔 둔다.
            "consumer_price": item.get("price"),
            "sale_price": item.get("sale_price"),
            "sale_percent": item.get("sale_percent"),
            "expect_sale_price": item.get("expect_sale_price"),
            # 매장 구분이다. 의류 분류가 아니라는 것을 이름으로 드러낸다.
            "store_category_no": item.get("root_category_no"),
            "store_category_name": item.get("root_category_name"),
            "ranking_scope": scope,
            "ranking_period": period,
            "calculated_at": calculated_at,
            # calculated_at 을 못 써서 수집 시각으로 떨어졌는지.
            "observed_at_fallback": not bool(
                calculated_at and _NAIVE_ISO_RE.match(calculated_at)),
            "rank_mismatch": site_rank != position,
            "url": PRODUCT_URL.format(item_id=item_id),
            "image_url": item.get("image_url"),
        }
        entity = f"{self.platform}:{item_id}"
        rank_key = f"{entity}@{scope}"

        # 둘 다 (상품, 순위 목록)의 속성이라 키에 범위가 들어간다. 상품
        # 자체의 속성(리뷰, 좋아요)은 하이버가 주지 않는다.
        metrics = (
            ("rank", rank, rank_key),
            ("rank_score", item.get("score"), rank_key),
        )
        for metric_type, value, key in metrics:
            if value is None:
                continue
            yield RawRecord(
                channel=self.channel,
                keyword_raw=name,
                entity=key,
                metric_type=metric_type,
                metric_value=value,
                observed_at=observed_at,
                metadata=metadata,
                run_id=run_id,
            )
