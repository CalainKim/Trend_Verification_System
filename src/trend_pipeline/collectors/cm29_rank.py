"""29CM 베스트 랭킹 수집기 (트랙 B 실시간 축적).

무신사 robots.txt 가 자체 수집기를 전면 차단하므로(docs/robots-compliance.md),
수집 허가가 나오기 전까지의 대체 소스다.

주의: 29CM 는 무신사 계열 서비스다(로그인이 member.one.musinsa.com SSO 를 쓰고
주문 일부가 www.musinsa.com/order-service 로 연결된다). 따라서 무신사와 29CM 를
'서로 독립적인 두 채널'로 세면 안 된다. 교차검증에서는 같은 커머스 채널로 묶고,
독립 채널은 네이버 검색과 쇼핑인사이트, Google Trends 쪽에서 확보한다.

수집 지표: 순위, 리뷰 수, 좋아요 수. 리뷰 수의 일별 증가량은 실제 구매를 거친
결과라 조작 여지가 적으므로 "순위는 올랐는데 리뷰 증가가 없다 -> 광고 효과 의심"
이라는 반증 신호로 쓴다.
"""

from __future__ import annotations

import time
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
# 상품 사진. API 가 주는 imageUrl 은 "/item/202511/....jpg" 꼴의 상대 경로다.
# ?width=N 을 붙이면 CDN 이 줄여서 준다. 160px webp 는 1.7KB 로 원본의 166분의
# 1이라 화면에 통째로 넣어도 부담이 없다. Referer 없이도 200 이 온다.
IMAGE_CDN = "https://img.29cm.co.kr"

#: 1차 분석 범위(상의) 카테고리. 3차 분류(티셔츠/후드/맨투맨)는 응답의
#: frontCategoryInfo.category3Name 으로 사후 필터링한다.
#:
#: **이 둘은 늘리지 않는다.** 봉인한 문제지 139건과 기저율 59.7% 가 이 범위로
#: 만들어졌고 검증 파트가 이 자료로 모델을 학습하고 있다. 여기에 코드를 하나
#: 더 넣으면 다음 빌드부터 기저율이 조용히 다른 숫자가 되고, 모델이 기준을
#: 넘었다는 결론이 근거를 잃는다. 넓히려면 아래 EXTRA 쪽에 넣는다.
TOPS_CATEGORY_CODES: Dict[str, str] = {
    "268103100": "여성의류>상의",
    "272103100": "남성의류>상의",
}

#: 2차 화면(카테고리를 넘는 유행)을 위해 더 모으는 범위. 2026-11-04 부터.
#:
#: 화면의 하의, 아우터, 신발은 지금까지 손으로 적은 예시였다. 예시로는
#: "카테고리를 넘는 유행" 이라는 2차의 주장이 서지 않는다. 순위는 소급 조회가
#: 안 되고 수집을 시작한 날부터만 쌓이므로 먼저 켠다. 속성 사전과 유형 규칙은
#: 뒤에 채워도 과거 상품명에 다시 돌릴 수 있다.
#:
#: 분석 쪽은 이 범위를 기본으로 보지 않는다. 보려면 그 자리에서 명시해야 한다.
EXTRA_CATEGORY_CODES: Dict[str, str] = {
    "268106100": "여성의류>바지",
    "272104100": "남성의류>하의",
    "268102100": "여성의류>아우터",
    "272102100": "남성의류>아우터",
    "270106100": "여성슈즈>스니커즈",
    "274101100": "남성슈즈>스니커즈",
}

#: 수집이 도는 전체 범위. 분석 범위와 다르다는 것이 요점이다.
ALL_CATEGORY_CODES: Dict[str, str] = {**TOPS_CATEGORY_CODES,
                                      **EXTRA_CATEGORY_CODES}

#: NOW=실시간, ONE_DAY=일간, ONE_WEEK=주간, ONE_MONTH=월간
PERIOD_SORTS = ("NOW", "ONE_DAY", "ONE_WEEK", "ONE_MONTH")

DEFAULT_USER_AGENT = (
    "TrendSignalResearchBot/0.1 "
    "(Ajou Univ. self-directed project; non-commercial research)"
)

#: API 가 한 번에 돌려주는 최대 건수(limit=200 을 보내도 100 만 온다)
MAX_PAGE_SIZE = 100


class Cm29RankCollector(Collector):
    """29CM 판매 순위를 받아 오는 수집기다. 상의 분류별 TOP 목록을 기록으로 바꾼다."""
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

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None,
             tries: int = 3) -> Any:
        """한 번 실패했다고 수집 전체를 버리지 않는다.

        29CM 은 가끔 최상위에 객체가 아니라 배열을 돌려준다. 그대로 두면
        payload.get 에서 AttributeError 가 나면서 그 회차가 통째로 죽는다.
        순위는 소급 조회가 안 되므로 죽은 회차의 자료는 영영 못 되찾는다.
        카테고리를 여덟로 늘리면 요청이 네 배라 이 자리를 더 자주 만난다.

        잠깐 쉬었다 다시 묻고, 그래도 안 되면 무엇이 왔는지 적고 멈춘다.
        조용히 빈 결과를 돌려주면 그날 순위가 없는 것과 구분이 안 된다.
        """
        last = ""
        for attempt in range(tries):
            self.sleep()
            resp = self.session.get(
                BASE_URL + path, params=params or {}, timeout=self.timeout_sec
            )
            resp.raise_for_status()
            payload = resp.json()
            if isinstance(payload, dict) and payload.get("result") == "SUCCESS":
                return payload["data"]
            if isinstance(payload, dict):
                raise RuntimeError(
                    f"29CM API 실패: {payload.get('message')} ({path}, {params})")
            # 객체가 아니다. 대개 잠시 뒤 다시 물으면 정상으로 온다.
            last = repr(payload)[:200]
            if attempt < tries - 1:
                time.sleep(2.0 * (attempt + 1))
        raise RuntimeError(
            f"29CM API 가 {tries}번 모두 객체가 아닌 것을 돌려줬다 "
            f"({path}, {params}): {last}")

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
        """분류마다 순위 목록을 받아 상품 하나당 기록을 만든다."""
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
        """29CM 응답의 상품 하나를 순위 기록으로 바꾼다. 가격, 할인율, 리뷰 같은 부가 정보는 metadata 에 담는다."""
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
            "image_url": (IMAGE_CDN + item["imageUrl"]) if item.get("imageUrl") else None,
            # 정가. lastSalePrice 는 할인된 값이라 둘이 있어야 할인액을 알 수 있다.
            "consumer_price": item.get("consumerPrice"),
        }
        entity = f"{self.platform}:{item_no}"

        # 순위는 (상품, 랭킹 목록)의 속성이고, 리뷰/좋아요는 상품 자체의 속성이다.
        # 유니섹스 상품은 여성과 남성 랭킹에 동시에 오르므로 순위 행의 키에
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
