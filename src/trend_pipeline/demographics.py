"""인구통계 쏠림 계산.

네이버쇼핑은 어느 키워드를 조회하든 40대가 최다로 나온다. 채널 이용자층이
그런 것이지 키워드의 특성이 아니다. 분포를 절대값으로 읽으면 모든 키워드가
'40대 트렌드'가 된다.

그래서 분야 전체 분포를 기준선으로 두고 그 대비로 읽는다.

    리프트 = 키워드의 그룹 점유율 / 분야 전체의 그룹 점유율

리프트가 1 이면 분야 평균과 같고, 2 면 그 그룹에 두 배로 쏠렸다는 뜻이다.
계획서의 검증 기준 "특정 연령·성별에 국한된 현상은 아닌지"는 이 값으로 읽는다.

여기서는 판정하지 않는다. 얼마나 쏠렸는지만 계산한다. 어느 정도부터 '국한'으로
볼지는 검증 단계가 정한다.
"""

from __future__ import annotations

import collections
import sqlite3
from dataclasses import dataclass
from typing import Dict, List, Optional

#: 리프트를 신뢰하려면 기준선 점유율이 이 정도는 돼야 한다. 기저가 거의 0 인
#: 그룹은 분모가 작아 리프트가 폭주한다(10대 같은 희소 그룹).
MIN_BASELINE_SHARE = 0.02


@dataclass(frozen=True)
class Skew:
    group: str
    observed_share: float
    baseline_share: float
    lift: float
    reliable: bool

    def __str__(self) -> str:
        mark = "" if self.reliable else "  (기저 희소, 참고용)"
        return (f"{self.group:<10} 점유 {self.observed_share:>6.1%} "
                f"기준 {self.baseline_share:>6.1%}  리프트 {self.lift:>5.2f}{mark}")


def daily_shares(
    conn: sqlite3.Connection,
    keyword_raw: str,
    prefix: str,
    channel: str = "naver_shopping",
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> Dict[str, float]:
    """그룹별 평균 점유율. 합이 1 이 되도록 맞춘다.

    점유율을 날짜별로 먼저 구한 뒤 평균낸다. 지수를 먼저 평균내고 나중에
    정규화하면 값이 큰 날이 과대 대표된다.

    빠진 그룹은 0 으로 채운다. 다른 그룹에 데이터가 있는 날에 특정 그룹만
    응답에서 빠졌다면 그날 그 그룹의 클릭은 0 에 가깝다는 뜻이다. 이를 건너뛰고
    '있던 날'만 평균내면 희소한 그룹일수록 평균이 부풀려진다. 그 그룹이 나타난
    날은 당연히 점유율이 높은 날이기 때문이다.
    """
    # 'gender=%' 로 매칭하면 교차셀('gender=m;ages=20')까지 걸려 같은 클릭이
    # 이중 계상된다. 주변분포만 봐야 하므로 구분자가 없는 entity 로 제한한다.
    sql = """
        SELECT observed_at, entity, metric_value
        FROM signal_raw
        WHERE channel = ? AND keyword_raw = ?
          AND entity LIKE ? AND entity NOT LIKE '%;%'
    """
    params = [channel, keyword_raw, f"{prefix}=%"]
    if start:
        sql += " AND observed_at >= ?"
        params.append(start)
    if end:
        sql += " AND observed_at < ?"
        params.append(end)
    rows = conn.execute(sql, params).fetchall()
    if not rows:
        return {}

    by_day: Dict[str, Dict[str, float]] = collections.defaultdict(dict)
    for r in rows:
        by_day[r["observed_at"]][r["entity"][len(prefix) + 1:]] = r["metric_value"]

    all_groups = {g for day in by_day.values() for g in day}
    acc: Dict[str, float] = {g: 0.0 for g in all_groups}
    n_days = 0
    for day_values in by_day.values():
        total = sum(day_values.values())
        if total <= 0:
            continue
        n_days += 1
        for group in all_groups:
            acc[group] += day_values.get(group, 0.0) / total
    if not n_days:
        return {}
    return {g: v / n_days for g, v in acc.items()}


def compare(
    observed: Dict[str, float], baseline: Dict[str, float]
) -> List[Skew]:
    """관측 점유율을 기준선 대비로 환산한다. 쏠린 순으로 돌려준다."""
    out = []
    for group in sorted(set(observed) | set(baseline)):
        o = observed.get(group, 0.0)
        b = baseline.get(group, 0.0)
        reliable = b >= MIN_BASELINE_SHARE
        lift = (o / b) if b > 0 else float("inf") if o > 0 else 0.0
        out.append(Skew(group, o, b, lift, reliable))
    out.sort(key=lambda s: -s.lift)
    return out


def overlap_window(
    conn: sqlite3.Connection, keyword_raw: str, category_code: str,
    prefix: str, channel: str = "naver_shopping",
) -> Optional[tuple]:
    """키워드와 기준선이 둘 다 존재하는 기간."""
    def span(name):
        r = conn.execute(
            "SELECT MIN(observed_at) a, MAX(observed_at) b FROM signal_raw "
            "WHERE channel=? AND keyword_raw=? AND entity LIKE ? AND entity NOT LIKE '%;%'",
            (channel, name, f"{prefix}=%")).fetchone()
        return (r["a"], r["b"]) if r and r["a"] else None

    a, b = span(keyword_raw), span(f"category:{category_code}")
    if not a or not b:
        return None
    start, end = max(a[0], b[0]), min(a[1], b[1])
    return (start, end) if start <= end else None


def profile(
    conn: sqlite3.Connection,
    keyword_raw: str,
    category_code: str,
    prefix: str = "age",
    channel: str = "naver_shopping",
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> List[Skew]:
    """키워드의 쏠림을 분야 기준선 대비로 계산한다.

    기준선과 관측치는 반드시 같은 기간에서 구한다. 기간이 다르면 비율이
    무의미해진다. 계절 상품은 시기만 달라도 분포가 크게 움직이기 때문이다.
    명시하지 않으면 둘 다 존재하는 구간으로 자동 제한한다.
    """
    if start is None and end is None:
        window = overlap_window(conn, keyword_raw, category_code, prefix, channel)
        if window is None:
            return []
        start, end = window[0], window[1] + "~"   # 마지막 날을 포함시키기 위한 상한

    observed = daily_shares(conn, keyword_raw, prefix, channel, start, end)
    baseline = daily_shares(conn, f"category:{category_code}", prefix, channel, start, end)
    if not observed or not baseline:
        return []
    return compare(observed, baseline)


def concentration(skews: List[Skew]) -> Optional[float]:
    """가장 쏠린 그룹의 리프트. 기저가 희소한 그룹은 제외한다.

    1 에 가까우면 분야 평균과 비슷하게 퍼져 있고, 크면 특정 집단에 몰려 있다.
    """
    usable = [s for s in skews if s.reliable]
    return max((s.lift for s in usable), default=None)
