"""수집 데이터 요약. 터미널 리포트와 대시보드가 같은 집계를 쓴다.

여기서는 판정을 하지 않는다. 무엇이 관측됐는지만 정리한다.
확정/보류/기각은 검증 단계(팀원)의 몫이다.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple, Sequence

from . import storage

#: 리뷰 증가량이 신호로 읽히려면 최소 이 정도 구간은 필요하다.
#: 리뷰는 구매 -> 배송 -> 작성을 거쳐 쌓이므로 며칠로는 거의 움직이지 않고,
#: 짧은 구간에서는 급상승 상품 대부분이 "리뷰 증가 0"으로 잡혀 신호가 무의미해진다.
MIN_REVIEW_WINDOW_DAYS = 7


def item_key(entity: str) -> str:
    """순위 entity('29cm:123@272103100')에서 상품 키('29cm:123')만 떼어낸다."""
    return entity.split("@", 1)[0]


@dataclass
class DayCoverage:
    """하루치 수집이 얼마나 들어왔는지를 담는다. 스냅샷이 0개면 그날은 빠진 날이다."""
    day: str
    n_snapshots: int
    n_rows: int

    @property
    def missing(self) -> bool:
        """그날 스냅샷이 하나도 없으면 참을 돌려준다."""
        return self.n_snapshots == 0


def coverage(conn: sqlite3.Connection, channel: str) -> List[DayCoverage]:
    """첫 수집일부터 마지막 수집일까지, 빠진 날을 포함해 하루씩 채운다.

    결측일을 눈에 보이게 하는 것이 목적이다. 크롤링은 소급 수집이 안 되므로
    빠진 날은 영구 손실이고, 늦게 발견할수록 손해가 커진다.
    """
    rows = list(
        conn.execute(
            """
            SELECT substr(observed_at, 1, 10)   AS day,
                   COUNT(DISTINCT observed_at)  AS n_snapshots,
                   COUNT(*)                     AS n_rows
            FROM signal_raw WHERE channel = ?
            GROUP BY day ORDER BY day
            """,
            (channel,),
        )
    )
    if not rows:
        return []
    seen = {r["day"]: DayCoverage(r["day"], r["n_snapshots"], r["n_rows"]) for r in rows}
    start = date.fromisoformat(rows[0]["day"])
    end = date.fromisoformat(rows[-1]["day"])
    out: List[DayCoverage] = []
    cur = start
    while cur <= end:
        key = cur.isoformat()
        out.append(seen.get(key, DayCoverage(key, 0, 0)))
        cur += timedelta(days=1)
    return out


@dataclass
class Item:
    """상품 하나의 날짜별 순위와 리뷰 수를 모은 묶음이다."""
    key: str
    name: str
    brand: str
    url: str
    category: str
    sold_out: bool = False
    ranks: Dict[str, int] = field(default_factory=dict)      # day -> rank
    reviews: Dict[str, int] = field(default_factory=dict)    # day -> review_count

    @property
    def days(self) -> List[str]:
        """이 상품이 순위에 잡힌 날짜를 오래된 순으로 돌려준다."""
        return sorted(self.ranks)

    def rank_delta(self, a: str, b: str) -> Optional[int]:
        """a -> b 순위 변화. 양수면 순위가 올라간 것(숫자가 작아진 것)."""
        if a not in self.ranks or b not in self.ranks:
            return None
        return self.ranks[a] - self.ranks[b]

    def review_delta(self, a: str, b: str) -> Optional[int]:
        """두 날짜 사이에 늘어난 리뷰 수를 돌려준다. 한쪽이라도 기록이 없으면 None 이다."""
        if a not in self.reviews or b not in self.reviews:
            return None
        return self.reviews[b] - self.reviews[a]


def build_items(
    conn: sqlite3.Connection,
    channel: str = "commerce_rank",
    ranking_category_code: Optional[str] = None,
    categories: Optional[Sequence[str]] = None,
) -> Tuple[List[str], Dict[str, Item]]:
    """관측일별로 스냅샷 하나씩만 골라 상품별 시계열을 만든다.

    한 날에 여러 스냅샷이 있어도 섞지 않는다. 섞으면 같은 날에 같은 순위가
    두 번 나타난다.

    categories 를 주지 않으면 persistence.ANALYSIS_CATEGORY_CODES(상의)만
    본다. 2026-11-04 부터 하의, 아우터, 신발도 모으는데, 여기 기본이 넓으면
    공개 대시보드가 그날 밤부터 말없이 섞인 것을 보여 준다. 넓게 보려면
    빈 튜플이나 코드 목록을 준다.

    ranking_category_code 는 코드 하나만 받던 옛 인자다. 주면 그쪽이 이긴다.
    """
    from . import persistence as _ps   # 순환 임포트를 피해 함수 안에서 읽는다

    codes = tuple(_ps.ANALYSIS_CATEGORY_CODES if categories is None
                  else categories)
    picks = storage.daily_snapshots(conn, channel, pick="last")
    days = [r["day"] for r in picks]
    if not days:
        return [], {}
    snapshot_at = {r["day"]: r["observed_at"] for r in picks}

    items: Dict[str, Item] = {}
    placeholders = ",".join("?" for _ in days)
    rows = conn.execute(
        f"""
        SELECT observed_at, entity, keyword_raw, metric_type, metric_value, metadata
        FROM signal_raw
        WHERE channel = ? AND observed_at IN ({placeholders})
          AND metric_type IN ('rank', 'review_count')
        """,
        (channel, *snapshot_at.values()),
    ).fetchall()

    day_of = {v: k for k, v in snapshot_at.items()}
    for row in rows:
        meta = json.loads(row["metadata"] or "{}")
        if row["metric_type"] == "rank":
            code = str(meta.get("ranking_category_code") or "")
            if ranking_category_code:
                if code != str(ranking_category_code):
                    continue
            elif codes and code not in codes:
                continue
        key = item_key(row["entity"])
        day = day_of[row["observed_at"]]
        item = items.get(key)
        if item is None:
            item = items[key] = Item(
                key=key,
                name=row["keyword_raw"],
                brand=meta.get("brand_kor") or meta.get("brand_eng") or "",
                url=meta.get("url", ""),
                category=meta.get("category3") or meta.get("category2") or "",
            )
        if row["metric_type"] == "rank":
            item.ranks[day] = int(row["metric_value"])
            item.sold_out = bool(meta.get("sold_out"))
        else:
            item.reviews[day] = int(row["metric_value"])

    # 순위 관측이 없는 상품(다른 카테고리에서만 잡힌 리뷰 행)은 제외
    return days, {k: v for k, v in items.items() if v.ranks}


def movers(
    items: Dict[str, Item], first_day: str, last_day: str, top: int = 10
) -> Tuple[List[Item], List[Item], List[Item]]:
    """(급상승, 급하락, 신규진입). 신규진입은 마지막 날에만 순위가 있는 상품."""
    both = [i for i in items.values() if first_day in i.ranks and last_day in i.ranks]
    both.sort(key=lambda i: i.rank_delta(first_day, last_day) or 0, reverse=True)
    risers = [i for i in both if (i.rank_delta(first_day, last_day) or 0) > 0][:top]
    fallers = [i for i in reversed(both) if (i.rank_delta(first_day, last_day) or 0) < 0][:top]
    new = [
        i for i in items.values()
        if last_day in i.ranks and first_day not in i.ranks
    ]
    new.sort(key=lambda i: i.ranks[last_day])
    return risers, fallers, new[:top]


def contradiction_signals(
    items: Dict[str, Item], first_day: str, last_day: str, min_rank_gain: int = 10
) -> List[Item]:
    """순위는 올랐는데 리뷰가 늘지 않은 상품.

    리뷰는 실제 구매를 거쳐야 쌓이므로 조작 여지가 적다. 순위만 오르고 리뷰가
    붙지 않으면 광고 노출이나 프로모션 효과를 의심할 근거가 된다.
    확정 판단이 아니라 검증 단계로 넘길 반증 후보를 표시하는 것이다.
    """
    out = []
    for item in items.values():
        gain = item.rank_delta(first_day, last_day)
        growth = item.review_delta(first_day, last_day)
        if gain is not None and growth is not None and gain >= min_rank_gain and growth <= 0:
            out.append(item)
    out.sort(key=lambda i: i.rank_delta(first_day, last_day) or 0, reverse=True)
    return out
