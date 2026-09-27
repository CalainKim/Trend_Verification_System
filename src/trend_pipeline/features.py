"""후보별 특징 추출.

검증 단계가 판정에 쓸 수치를 계산한다. 여기서는 판정하지 않는다.
"확정할 만한가"가 아니라 "무엇이 관측됐는가"만 낸다.

모든 계산은 as_of 이전 데이터만 쓴다. 이 인자를 필수로 둔 이유가 있다.
누수 차단이 내보내기 단계에만 있으면, 특징 계산이 이후 데이터를 한 번 보는
순간 이미 오염된다. 시점을 인자로 강제하면 "언제 기준 특징인가"가 호출부에
드러나고, 빠뜨릴 수 없다.
"""

from __future__ import annotations

import json
import sqlite3
import statistics
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional

from . import demographics as dg

#: 급상승을 재는 기본 창. 최근 RECENT 일을 직전 BASE 일과 비교한다.
RECENT_DAYS = 7
BASE_DAYS = 28


@dataclass
class ChannelTrend:
    channel: str
    entity: str
    n_days: int
    coverage: float           # 조회 구간 대비 실제 관측 일수
    recent_mean: Optional[float]
    base_mean: Optional[float]
    change_ratio: Optional[float]   # 최근 / 직전. 1 보다 크면 상승
    slope: Optional[float]          # 최근 구간 하루당 변화량
    last_value: Optional[float]


@dataclass
class CaseFeatures:
    keyword: str
    as_of: str
    window_start: str
    channels: Dict[str, ChannelTrend] = field(default_factory=dict)
    age_lift: Dict[str, float] = field(default_factory=dict)
    gender_lift: Dict[str, float] = field(default_factory=dict)
    top_age_lift: Optional[float] = None
    segment_change_ratio: Optional[float] = None   # 20대 남성 등
    seasonality_ratio: Optional[float] = None      # 전년 동기 대비
    channel_count: int = 0
    notes: List[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True)


def _series(
    conn: sqlite3.Connection, keyword: str, channel: str, entity: str,
    start: str, end: str, metric_type: Optional[str] = None,
) -> List[tuple]:
    """(observed_at, value) 오름차순. end 는 포함하지 않는다."""
    sql = """
        SELECT observed_at, AVG(metric_value) AS v
        FROM signal_raw
        WHERE keyword_raw = ? AND channel = ? AND entity = ?
          AND observed_at >= ? AND observed_at < ?
    """
    params = [keyword, channel, entity, start, end]
    if metric_type:
        sql += " AND metric_type = ?"
        params.append(metric_type)
    sql += " GROUP BY observed_at ORDER BY observed_at"
    return [(r["observed_at"], r["v"]) for r in conn.execute(sql, params)]


def _slope(points: List[tuple]) -> Optional[float]:
    """최소제곱 기울기. 하루당 변화량."""
    if len(points) < 3:
        return None
    xs = list(range(len(points)))
    ys = [p[1] for p in points]
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom


def channel_trend(
    conn: sqlite3.Connection, keyword: str, channel: str, entity: str,
    as_of: str, recent_days: int = RECENT_DAYS, base_days: int = BASE_DAYS,
    metric_type: Optional[str] = None,
) -> Optional[ChannelTrend]:
    cut = date.fromisoformat(as_of[:10])
    recent_start = cut - timedelta(days=recent_days)
    base_start = recent_start - timedelta(days=base_days)

    window = _series(conn, keyword, channel, entity,
                     base_start.isoformat(), cut.isoformat(), metric_type)
    if not window:
        return None

    recent = [p for p in window if p[0][:10] >= recent_start.isoformat()]
    base = [p for p in window if p[0][:10] < recent_start.isoformat()]

    recent_mean = statistics.fmean(v for _, v in recent) if recent else None
    base_mean = statistics.fmean(v for _, v in base) if base else None
    ratio = None
    if recent_mean is not None and base_mean:
        ratio = recent_mean / base_mean

    return ChannelTrend(
        channel=channel,
        entity=entity,
        n_days=len(window),
        coverage=len(window) / (recent_days + base_days),
        recent_mean=recent_mean,
        base_mean=base_mean,
        change_ratio=ratio,
        slope=_slope(recent),
        last_value=window[-1][1] if window else None,
    )


def seasonality(
    conn: sqlite3.Connection, keyword: str, channel: str, entity: str, as_of: str,
) -> Optional[float]:
    """전년 동기 대비. 1 에 가까우면 작년에도 같은 시기에 올랐다는 뜻이다.

    계절 반복을 트렌드로 착각하는 것을 막는 반증 축이다.
    """
    cut = date.fromisoformat(as_of[:10])
    now = channel_trend(conn, keyword, channel, entity, cut.isoformat())
    then = channel_trend(conn, keyword, channel, entity,
                         (cut - timedelta(days=365)).isoformat())
    if not now or not then or not now.change_ratio or not then.change_ratio:
        return None
    return now.change_ratio / then.change_ratio


def extract(
    conn: sqlite3.Connection,
    keyword: str,
    as_of: str,
    shopping_category: Optional[str] = None,
    segment_entity: Optional[str] = None,
    window_days: int = RECENT_DAYS + BASE_DAYS,
) -> CaseFeatures:
    """as_of 이전 데이터만으로 후보의 특징을 낸다."""
    cut = date.fromisoformat(as_of[:10])
    feats = CaseFeatures(
        keyword=keyword,
        as_of=cut.isoformat(),
        window_start=(cut - timedelta(days=window_days)).isoformat(),
    )

    probes = [
        ("naver_datalab", "", "search_index", "검색"),
        ("naver_shopping", "", "click_index", "쇼핑클릭"),
        ("commerce_rank", None, "rank", "커머스순위"),
    ]
    for channel, entity, metric, label in probes:
        if entity is None:      # 커머스는 entity 가 상품별이라 지금은 건너뛴다
            continue
        t = channel_trend(conn, keyword, channel, entity, cut.isoformat(),
                          metric_type=metric)
        if t:
            feats.channels[label] = t

    feats.channel_count = len(feats.channels)

    if segment_entity:
        t = channel_trend(conn, keyword, "naver_datalab", segment_entity,
                          cut.isoformat(), metric_type="search_index")
        if t:
            feats.channels[f"검색·{segment_entity}"] = t
            feats.segment_change_ratio = t.change_ratio
            if t.coverage < 0.5:
                feats.notes.append(
                    f"세그먼트 커버리지 {t.coverage:.0%}. 결측이 많아 추세 판단이 어렵다")

    if shopping_category:
        age = dg.profile(conn, keyword, shopping_category, prefix="age")
        gender = dg.profile(conn, keyword, shopping_category, prefix="gender")
        feats.age_lift = {s.group: round(s.lift, 3) for s in age if s.reliable}
        feats.gender_lift = {s.group: round(s.lift, 3) for s in gender if s.reliable}
        feats.top_age_lift = dg.concentration(age)
        if age and not feats.age_lift:
            feats.notes.append("연령 기준선이 모두 희소해 리프트를 신뢰할 수 없다")

    feats.seasonality_ratio = seasonality(
        conn, keyword, "naver_datalab", "", cut.isoformat())
    if feats.seasonality_ratio is None:
        feats.notes.append("전년 동기 자료가 없어 계절성을 확인할 수 없다")

    if feats.channel_count < 2:
        feats.notes.append(
            f"관측된 독립 채널이 {feats.channel_count}개다. 교차검증이 성립하지 않는다")
    return feats


def save(conn: sqlite3.Connection, candidate_id: str, feats: CaseFeatures) -> None:
    """candidate_summary 에 저장한다. 같은 (후보, 시점)이면 덮어쓴다."""
    search = feats.channels.get("검색")
    shopping = feats.channels.get("쇼핑클릭")
    conn.execute(
        """
        INSERT OR REPLACE INTO candidate_summary
            (candidate_id, date, musinsa_rank_change, review_growth_rate,
             naver_search_index_change, demographic_distribution,
             gtrends_lead_days, channel_count)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        (candidate_id, feats.as_of, None, None,
         search.change_ratio if search else None,
         feats.to_json(), None, feats.channel_count),
    )
    conn.commit()
