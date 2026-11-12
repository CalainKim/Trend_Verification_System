"""코오롱몰 베스트 랭킹 수집기 (두 번째 커머스 채널).

왜 코오롱몰인가
---------------
11월 역할 분담에는 "지그재그를 붙인다" 고 적혀 있었다. 2026-11-05 에 다시
받아 보니 지그재그 robots.txt 가 9월과 달라져서 `User-agent: *` 가
`Disallow: /` 로 바뀌었다. 무신사와 같은 화이트리스트 구조다. 그래서
대체 소스를 여덟 곳 확인하고 코오롱몰을 골랐다. 근거는
`docs/robots-compliance.md` 의 "재확인 2026-11-05" 절에 적었다.

고른 이유는 셋이다.

    브랜드가 구조화돼 있다   supplierBrandName 이 따로 온다. 하이버는
                           상품명에서 파싱해야 한다
    순위가 서버에 박혀 온다   한 번 GET 하면 100건이 HTML 안에 들어 있다
    운영사가 독립이다        29CM 는 무신사 계열이라 교차 채널로 셀 수 없다.
                           코오롱몰은 셀 수 있다

세 번째가 이 프로젝트에서 제일 크다. `cm29_rank` 주석에 적힌 대로 29CM 와
무신사는 같은 커머스 채널로 묶어야 해서, 지금까지 커머스는 사실상 한
채널이었다. 코오롱몰이 들어오면 "두 커머스가 같은 방향" 이라는 근거가
처음으로 생긴다.

채널을 왜 따로 두는가
--------------------
검증 파트가 지금 자료로 리즈닝 모델을 학습하고 있다. 봉인한 문제지 139건과
기저율 59.7% 가 `commerce_rank` 의 상의 범위로 만들어졌다. 그 범위가 한
행이라도 움직이면 "기준을 넘었다" 는 결론이 근거를 잃는다.

그래서 코오롱몰을 `commerce_rank` 에 섞지 않고 `kolon_rank` 라는 별도
채널에 넣는다. `persistence.load_series` 와 `_item_scope_sql` 이 전부
`channel = ?` 로 걸리므로, 채널이 다르면 기존 질의가 **구조적으로** 안
바뀐다. 카테고리 코드로 거르는 방식은 코드가 우연히 겹치면 조용히 새는데
이 방식은 그 경로가 없다.

분석에 넣는 것은 뒤에 눈에 보이는 선택으로 한다. 지금은 쌓기만 한다.
순위는 소급 조회가 안 되므로 쌓는 것만 늦출 수 없다.

무엇을 모으고 무엇을 안 모으는가
------------------------------
베스트 목록은 상위 탭 단위로만 나뉘고 의류 소분류가 없다. `stdCategoryLevel`
필드를 요청은 하지만 응답이 전부 null 로 온다. 그래서 상의만 따로 받을 수
없다. 유형 분류는 상품명으로 사후에 한다. 이 저장소가 이미 `TYPE_RULES` 로
그렇게 하고 있어서 방식이 일관된다.

아울렛과 라이프 탭은 안 모은다. 아울렛 순위는 유행이 아니라 재고 소진을
가리키고, 라이프는 바디워시와 치약과 담요라서 의류가 아니다. 모으면 유행
신호가 오염된다.

29CM 과 다른 점
--------------
리뷰 수가 없다. `cm29_rank` 는 "순위는 올랐는데 리뷰 증가가 없다 ->
광고 효과 의심" 을 반증 신호로 쓰는데 코오롱몰에는 그 자리에 쓸 값이
없다. 좋아요(wishProductCount)만 있다. 반대로 29CM 에 없는 것이 온다.

    supplierOwnFlag   자사 브랜드인지. 자사 밀어주기를 걸러낼 수 있다
    season            FOURSEASONS, WINTER 등
    produceYear       생산 연도. 재고 소진인지 신상 유행인지 가른다

robots 근거
----------
2026-11-05 확인 결과 kolonmall.com/robots.txt 에는 `User-agent: *` 그룹이
아예 없다. RFC 9309 는 내 수집기에 맞는 그룹이 하나도 없으면 제한 규칙이
없는 것으로 읽는다. 다만 이것은 명시적 허락이 아니라 규칙의 부재이므로
29CM 의 `Allow: /` 와 구분해서 적어야 한다.

명시된 봇들에게 `/api/rest` 와 `/graphql` 을 막아 둔 뜻은 존중한다. 우리에게
적용되는 규칙이 없어도 그 두 경로는 쓰지 않고, 사이트맵에 올라와 있는 페이지
경로만 쓴다. `/Best` 가 서버 렌더링이라 그것으로 충분하다.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

import requests

from ..models import RawRecord
from .base import Collector

KST = timezone(timedelta(hours=9))

BEST_URL = "https://www.kolonmall.com/Best"
PRODUCT_URL = "https://www.kolonmall.com/Product/{code}"

#: 수집하는 베스트 탭. 키가 `/Best?categoryCode=` 에 그대로 들어간다.
#: "ALL" 은 쿼리 없이 받는 통합 목록이라 코드가 없다.
#:
#: 탭마다 totalCount 가 285 에서 300 사이다. 전체 카탈로그를 거른 것이
#: 아니라 베스트 자체가 탭당 300건 안쪽이라는 뜻이다.
BEST_SCOPES: Dict[str, str] = {
    "ALL": "전체",
    "133010010000": "남성",
    "133010020000": "여성",
    "133010060000": "스포츠/아웃도어",
}

#: 일부러 안 모으는 탭. 지우지 말고 왜 뺐는지 남겨 둔다.
EXCLUDED_SCOPES: Dict[str, str] = {
    "133010030000": "아울렛 (할인 재고라 순위가 유행이 아니라 재고 소진을 가리킨다)",
    "133010040000": "라이프 (바디워시, 치약, 담요. 의류가 아니다)",
}

DEFAULT_USER_AGENT = (
    "TrendSignalResearchBot/0.1 "
    "(Ajou Univ. self-directed project; non-commercial research)"
)

#: 서버가 1쪽만 그려 준다. `?page=2` 는 빈 화면이 온다.
#: 29CM 수집기도 TOP100 만 받으므로 두 채널의 깊이가 같다.
MAX_PAGE_SIZE = 100

#: 응답 안에서 베스트 블록을 찾는 표식.
#:
#: 공백을 허용한다. 실제 응답은 공백 없는 JSON 이지만 사이트가 어느 날
#: 직렬화를 바꾸면 고정 문자열은 아무것도 못 찾고, 그러면 수집기가 그날
#: 순위를 빈 것으로 보고 예외를 던진다. 순위는 소급 조회가 안 되니 그
#: 하루는 영구 손실이다. 사라질 이유를 줄여 둔다.
_BEST_MARK_RE = re.compile(r'"__typename"\s*:\s*"bestItems"')


def _json_object_at(text: str, start: int) -> Optional[str]:
    """`start` 의 '{' 부터 짝이 맞는 '}' 까지 잘라낸다.

    정규식으로는 할 수 없다. 중첩이 있고 문자열 리터럴 안에 중괄호가 들어
    있기 때문이다. 따옴표 안을 건너뛰면서 깊이를 센다.

    되돌릴 짝을 못 찾으면 None 이다. 깨진 응답을 통째로 파싱 시도해서
    엉뚱한 자리에서 터지는 것보다 여기서 멈추는 쪽이 낫다.
    """
    if start < 0 or start >= len(text) or text[start] != "{":
        return None
    depth = 0
    in_quote = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_quote = False
            continue
        if ch == '"':
            in_quote = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def parse_best(html: str) -> Tuple[List[Dict[str, Any]], Optional[int]]:
    """`/Best` 응답에서 상품 목록과 전체 건수를 뽑는다.

    GraphQL 응답이 HTML 안에 그대로 직렬화돼 있다. 같은 블록이 서버 렌더링과
    수화(hydration) 때문에 두 번 실려 오므로 상품 코드로 중복을 지운다.
    지우지 않으면 100건이 200건으로 보이고 순위가 두 배로 어긋난다.

    순서가 곧 순위다. dict 로 모으지 않고 등장 순서를 유지한다.
    """
    items: List[Dict[str, Any]] = []
    seen: set = set()
    total: Optional[int] = None

    for mark in _BEST_MARK_RE.finditer(html):
        start = html.rfind("{", 0, mark.start())
        raw = _json_object_at(html, start)
        if raw is None:
            continue
        try:
            block = json.loads(raw)
        except json.JSONDecodeError:
            continue
        page = block.get("page") or {}
        if total is None and isinstance(page.get("totalCount"), int):
            total = page["totalCount"]
        for item in block.get("results") or []:
            code = item.get("code")
            if not code or code in seen:
                continue
            seen.add(code)
            items.append(item)
    return items, total


class KolonRankCollector(Collector):
    """코오롱몰 판매 순위를 받아 오는 수집기다."""
    channel = "kolon_rank"
    platform = "kolonmall"

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        min_interval_sec: float = 2.0,
        timeout_sec: float = 40.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        super().__init__()
        self.min_interval_sec = min_interval_sec
        self.timeout_sec = timeout_sec
        self.session = session or requests.Session()
        # 응답이 1.6MB 라 gzip 을 받는다. requests 가 알아서 풀어 준다.
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ko-KR,ko;q=0.9",
            "Referer": "https://www.kolonmall.com/",
        })

    # ------------------------------------------------------------------ HTTP

    def fetch_best(self, scope: str = "ALL", tries: int = 3
                   ) -> Tuple[List[Dict[str, Any]], Optional[int]]:
        """베스트 탭 하나를 받아 상품 목록으로 돌려준다.

        순위는 소급 조회가 안 된다. 한 번 실패했다고 그 회차를 버리면 그날
        자료는 영영 못 되찾으므로 쉬었다 다시 묻는다. 그래도 안 되면
        무엇이 왔는지 적고 멈춘다. 조용히 빈 목록을 돌려주면 "그날 순위가
        없었다" 와 구분이 안 된다.
        """
        params = {} if scope == "ALL" else {"categoryCode": scope}
        last = ""
        for attempt in range(tries):
            self.sleep()
            resp = self.session.get(
                BEST_URL, params=params, timeout=self.timeout_sec)
            resp.raise_for_status()
            items, total = parse_best(resp.text)
            if items:
                return items, total
            last = (f"HTTP {resp.status_code}, {len(resp.text)}자, "
                    f"bestItems 표식 {len(_BEST_MARK_RE.findall(resp.text))}개")
            if attempt < tries - 1:
                time.sleep(2.0 * (attempt + 1))
        raise RuntimeError(
            f"코오롱몰 베스트에서 상품을 못 뽑았다 (scope={scope}): {last}")

    # ------------------------------------------------------------- 시점 계산

    @staticmethod
    def observed_at_for(now: Optional[datetime] = None) -> str:
        """관측 시점. 수집 실행 하나가 스냅샷 하나다.

        `cm29_rank.observed_at_for` 와 같은 이유로 초 단위까지 적는다.
        날짜만 적으면 하루 두 번 수집할 때 두 실행이 같은 키로 충돌하고,
        UNIQUE 제약이 1차 실행값을 지키는 사이 새로 진입한 상품만 통과해서
        한 날짜 안에 서로 다른 시점의 순위가 섞인다.
        """
        now = now or datetime.now(KST)
        return now.astimezone(KST).replace(microsecond=0).isoformat()

    # --------------------------------------------------------------- 수집

    def collect(
        self,
        scopes: Optional[Sequence[str]] = None,
        max_items: int = MAX_PAGE_SIZE,
        run_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> Iterator[RawRecord]:
        """탭을 돌면서 레코드를 내놓는다.

        `observed_at` 을 탭 루프 **밖에서** 한 번만 계산한다. 안에서 계산하면
        탭마다 몇 초씩 달라져서 같은 회차가 여러 시점으로 쪼개지고, 일 단위
        스냅샷 고르기가 탭별로 어긋난다.
        """
        picked = list(scopes) if scopes else list(BEST_SCOPES)
        observed_at = self.observed_at_for(now)

        for scope in picked:
            items, _total = self.fetch_best(scope)
            for rank, item in enumerate(items[:max_items], start=1):
                yield from self._to_records(item, rank, scope, observed_at, run_id)

    def _to_records(
        self,
        item: Dict[str, Any],
        rank: int,
        scope: str,
        observed_at: str,
        run_id: Optional[str],
    ) -> Iterator[RawRecord]:
        """코오롱몰 응답의 상품 하나를 순위 기록으로 바꾼다. 정가와 할인가 이름을 29CM 와 같게 맞춘다."""
        code = item.get("code")
        name = (item.get("name") or "").strip()
        if not code or not name:
            return

        price = item.get("price") or {}
        metadata = {
            "platform": self.platform,
            "product_code": code,
            "brand_kor": item.get("supplierBrandName"),
            "supplier_code": item.get("supplierCode"),
            # 자사 브랜드 여부. 자사 밀어주기로 오른 순위를 걸러낼 때 쓴다.
            "supplier_own": bool(item.get("supplierOwnFlag")),
            "color": item.get("color"),
            "sold_out": item.get("soldOutYn") == "Y",
            "is_new": bool(item.get("newProductYn")),
            # wishPrice 가 정가이고 price 가 할인가다. 29CM 과 이름이 반대라
            # 여기서 맞춰 둔다. 안 맞추면 화면이 할인액을 음수로 그린다.
            "sale_price": price.get("price"),
            "consumer_price": price.get("wishPrice"),
            "sale_percent": price.get("discountRate"),
            "season": item.get("season"),
            "produce_year": item.get("produceYear"),
            "ranking_scope": scope,
            "ranking_scope_name": BEST_SCOPES.get(scope, ""),
            "url": PRODUCT_URL.format(code=code),
            "image_url": item.get("representationImage"),
        }
        entity = f"{self.platform}:{code}"

        # 순위는 (상품, 베스트 탭)의 속성이고 좋아요는 상품 자체의 속성이다.
        # 한 상품이 전체와 남성 탭에 동시에 오르므로 순위 행의 키에 탭을
        # 넣어야 한 쪽이 UNIQUE 제약에 걸려 사라지지 않는다. 좋아요는 어느
        # 탭에서 보든 같은 값이라 상품 단위로 한 번만 저장한다.
        #
        # 리뷰 수는 코오롱몰에 없다. 없는 지표를 0 으로 채우면 "리뷰가 안
        # 늘었다" 는 반증 신호가 모든 상품에서 참이 되어 버린다.
        metrics = (
            ("rank", rank, f"{entity}@{scope}"),
            ("heart_count", item.get("wishProductCount"), entity),
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
