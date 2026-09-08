"""29CM 베스트 랭킹 수집기 (트랙 B · 실시간 축적).

무신사 robots.txt 가 자체 수집기를 전면 차단하므로(docs/robots-compliance.md),
수집 허가가 나오기 전까지의 대체 소스다.

주의: 29CM 는 무신사 계열 서비스다(로그인이 member.one.musinsa.com SSO 를 쓰고
주문 일부가 www.musinsa.com/order-service 로 연결된다). 따라서 무신사와 29CM 를
'서로 독립적인 두 채널'로 세면 안 된다. 교차검증에서는 같은 커머스 채널로 묶고,
독립 채널은 네이버 검색/쇼핑인사이트·Google Trends 쪽에서 확보한다.

수집 지표: 순위, 리뷰 수, 좋아요 수. 리뷰 수의 일별 증가량은 실제 구매를 거친
결과라 조작 여지가 적으므로 "순위는 올랐는데 리뷰 증가가 없다 -> 광고 효과 의심"
이라는 반증 신호로 쓴다.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterator, List, Optional, Sequence

import requests

from ..models import RawRecord
from .base import Collector

KST = timezone(timedelta(hours=9))

BASE_URL = "https://recommend-api.29cm.co.kr"
CATEGORIES_PATH = "/api/v4/best/categories"
ITEMS_PATH = "/api/v4/best/items"
PRODUCT_URL = "https://product.29cm.co.kr/catalog/{item_no}"

#: 1차 분석 범위(상의) 카테고리. 3차 분류(티셔츠/후드/맨투맨)는 응답의
#: frontCategoryInfo.category3Name 으로 사후 필터링한다.
TOPS_CATEGORY_CODES: Dict[str, str] = {
    "268103100": "여성의류>상의",
    "272103100": "남성의류>상의",
}

#: NOW=실시간, ONE_DAY=일간, ONE_WEEK=주간, ONE_MONTH=월간
PERIOD_SORTS = ("NOW", "ONE_DAY", "ONE_WEEK", "ONE_MONTH")

DEFAULT_USER_AGENT = (
    "TrendSignalResearchBot/0.1 "
    "(Ajou Univ. self-directed project; non-commercial research)"
)

#: API 가 한 번에 돌려주는 최대 건수(limit=200 을 보내도 100 만 온다)
MAX_PAGE_SIZE = 100


class Cm29RankCollector(Collector):
    channel = "commerce_rank"
    platform = "29cm"

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        min_interval_sec: float = 1.5,
        timeout_sec: float = 20.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        super().__init__()
        self.min_interval_sec = min_interval_sec
        self.timeout_sec = timeout_sec
        self.session = session or requests.Session()
        self.session.headers.update(
            {"User-Agent": user_agent, "Referer": "https://www.29cm.co.kr/"}
        )

    # ------------------------------------------------------------------ HTTP

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        self.sleep()
        resp = self.session.get(
            BASE_URL + path, params=params or {}, timeout=self.timeout_sec
        )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("result") != "SUCCESS":
            raise RuntimeError(f"29CM API 실패: {payload.get('message')} ({path}, {params})")
        return payload["data"]

    def fetch_categories(self, parent_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """parent_code 가 없으면 대분류, 있으면 그 아래 중분류 목록."""
        params = {"categoryList": parent_code} if parent_code else None
        return self._get(CATEGORIES_PATH, params)

    def fetch_items(
        self,
        category_code: str,
        period_sort: str = "ONE_DAY",
        max_items: int = MAX_PAGE_SIZE,
        gender: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """랭킹 상위 max_items 개를 순위 순서대로 반환한다."""
        if period_sort not in PERIOD_SORTS:
            raise ValueError(f"period_sort 는 {PERIOD_SORTS} 중 하나여야 한다: {period_sort!r}")

        items: List[Dict[str, Any]] = []
        offset = 0
        while len(items) < max_items:
            page_size = min(MAX_PAGE_SIZE, max_items - len(items))
            params: Dict[str, Any] = {
                "categoryList": category_code,
                "periodSort": period_sort,
                "limit": page_size,
                "offset": offset,
            }
            if gender:
                params["gender"] = gender
            content = self._get(ITEMS_PATH, params).get("content") or []
            items.extend(content)
            if len(content) < page_size:
                break  # 더 이상 없음
            offset += len(content)
        return items[:max_items]

    # ------------------------------------------------------------- 시점 계산

    @staticmethod
    def observed_at_for(period_sort: str, now: Optional[datetime] = None) -> str:
        """관측 시점. 수집 실행 하나가 곧 스냅샷 하나다.

        날짜만 기록하면 하루 두 번 수집할 때 두 실행이 같은 키로 충돌한다.
        UNIQUE 제약이 1차 실행값을 지키는 사이 그동안 랭킹에 새로 진입한 상품만
        통과해서, 한 날짜 안에 서로 다른 시점의 순위가 섞이고 같은 순위가
        두 번 나타난다. 부분 실패한 실행이 그날 데이터를 영구히 오염시키는
        경로이기도 하다.

        그래서 KST 초 단위까지 기록해 실행마다 독립된 스냅샷이 되게 한다.
        하루 두 번 수집은 중복이 아니라 이중화가 되고, 일 단위 분석은
        그날의 스냅샷 중 하나를 고르면 된다(daily_snapshots 참고).
        """
        now = now or datetime.now(KST)
        return now.astimezone(KST).replace(microsecond=0).isoformat()

    # --------------------------------------------------------------- 수집

    def collect(
        self,
        category_codes: Optional[Sequence[str]] = None,
        period_sort: str = "ONE_DAY",
        max_items: int = MAX_PAGE_SIZE,
        gender: Optional[str] = None,
        run_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> Iterator[RawRecord]:
        codes = list(category_codes) if category_codes else list(TOPS_CATEGORY_CODES)
        observed_at = self.observed_at_for(period_sort, now)

        for code in codes:
            items = self.fetch_items(code, period_sort, max_items, gender)
            for rank, item in enumerate(items, start=1):
                yield from self._to_records(item, rank, code, period_sort, observed_at, run_id)

    def _to_records(
        self,
        item: Dict[str, Any],
        rank: int,
        category_code: str,
        period_sort: str,
        observed_at: str,
        run_id: Optional[str],
    ) -> Iterator[RawRecord]:
        item_no = item.get("itemNo")
        name = (item.get("itemName") or "").strip()
        if item_no is None or not name:
            return

        cat = (item.get("frontCategoryInfo") or [{}])[0]
        metadata = {
            "platform": self.platform,
            "item_no": item_no,
            "brand_kor": item.get("frontBrandNameKor"),
            "brand_eng": item.get("frontBrandNameEng"),
            "brand_no": item.get("frontBrandNo"),
            "sold_out": bool(item.get("isSoldOut")),
            "is_new": bool(item.get("isNew")),
            "sale_price": item.get("lastSalePrice"),
            "sale_percent": item.get("lastSalePercent"),
            "review_avg": item.get("reviewAveragePoint"),
            "ranking_category_code": category_code,
            "ranking_category_name": TOPS_CATEGORY_CODES.get(category_code, ""),
            "category1": cat.get("category1Name"),
            "category2": cat.get("category2Name"),
            "category3": cat.get("category3Name"),
            "category3_code": cat.get("category3Code"),
            "period_sort": period_sort,
            "url": PRODUCT_URL.format(item_no=item_no),
        }
        entity = f"{self.platform}:{item_no}"

        # 순위는 (상품, 랭킹 목록)의 속성이고, 리뷰/좋아요는 상품 자체의 속성이다.
        # 유니섹스 상품은 여성·남성 랭킹에 동시에 오르므로 순위 행의 키에
        # 랭킹 목록을 포함시켜야 한 쪽이 유실되지 않는다. 반대로 리뷰/좋아요는
        # 어느 목록에서 보든 같은 값이라 상품 단위로 한 번만 저장한다.
        metrics = (
            ("rank", rank, f"{entity}@{category_code}"),
            ("review_count", item.get("reviewCount"), entity),
            ("heart_count", item.get("heartCount"), entity),
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
