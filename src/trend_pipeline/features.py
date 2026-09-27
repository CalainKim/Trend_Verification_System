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
import re
import statistics
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional

from . import demographics as dg, vectorstore

#: 급상승을 재는 기본 창. 최근 RECENT 일을 직전 BASE 일과 비교한다.
RECENT_DAYS = 7
BASE_DAYS = 28

#: 후보와 상품을 잇는 기준. 유사도 하나로는 가를 수 없어서 하이브리드로 간다.
#:
#: 실측에서 정답과 오답의 유사도가 겹쳤다. '맨투맨'에 대한 진짜 맨투맨 상품이
#: 0.803, '럭비티'에 대한 엉뚱한 블라우스가 0.79 였다. 임계값 하나로 가를 수
#: 있는 구간이 없다. 밀집 벡터 검색만으로는 해결되지 않는다.
#:
#: 그래서 벡터로 후보를 넓게 뽑고 어휘적 근거로 거른다. 키워드가 상품명에
#: 글자 그대로 있으면 낮은 유사도에서도 받고, 없으면 아주 높은 유사도를 요구한다.
MATCH_RECALL_SIMILARITY = 0.75      # 벡터로 후보를 뽑는 하한
MATCH_STRICT_SIMILARITY = 0.88      # 어휘 근거가 없을 때 요구하는 하한
#: 어휘 근거가 있으면 유사도 하한을 두지 않는다. 벡터 점수를 거부권으로 쓰면
#: 점수가 애매하게 낮은 상품이 점수가 아예 없는 상품보다 불리해진다.

#: 후보 하나에 붙일 상품 수 상한.
MATCH_LIMIT = 20


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
class CommerceSignal:
    """커머스에서 관측된 것. 후보 키워드와 상품은 벡터 검색으로 잇는다."""
    matched_items: int
    rank_improved: int            # 순위가 오른 상품 수
    rank_worsened: int
    mean_rank_change: Optional[float]      # 양수면 순위가 올랐다는 뜻
    review_growth_total: Optional[int]
    items_with_review_growth: int
    sold_out: int
    contradiction: bool           # 순위는 올랐는데 리뷰가 안 늘었다
    examples: List[str] = field(default_factory=list)


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
    commerce: Optional[CommerceSignal] = None
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


def _tokens(text: str) -> set:
    """비교용 토큰. 정규화로 프로모션 태그·품번·색상을 걷어낸 뒤 나눈다."""
    from . import embeddings

    cleaned = embeddings.normalize_for_embedding(text).lower()
    return {t for t in re.split(r"[^0-9a-z가-힣]+", cleaned) if len(t) >= 2}


def _flat(text: str) -> str:
    """구분자만 제거한 문자열. 토큰 순서를 보존한다.

    set 을 join 하면 안 된다. 파이썬은 문자열 해시를 프로세스마다 무작위화하므로
    이어붙인 순서가 실행마다 달라지고, 같은 입력에 다른 답이 나온다.
    실제로 '후드 티셔츠' 가 어떤 실행에서는 '후드티' 에 매칭되고 어떤 실행에서는
    안 됐다. 재현 가능성이 이 연구의 평가 기준이라 그냥 넘길 수 없는 종류다.
    """
    from . import embeddings

    return re.sub(r"[^0-9a-z가-힣]+", "",
                  embeddings.normalize_for_embedding(text).lower())


#: 한영 표기 대응. 임베딩이 '후드티'와 'HOODIE' 를 가깝게 두지 않고 글자도
#: 겹치지 않아 두 경로 모두 놓친다. 1차 분석 범위(티셔츠·후드·맨투맨)에
#: 해당하는 것만 손으로 적는다. 범위를 넓힐 때 함께 늘린다.
BILINGUAL = {
    "후드": ("hood", "hoodie", "hooded"),
    "후드티": ("hood", "hoodie", "hooded"),
    "후디": ("hood", "hoodie", "hooded"),
    "맨투맨": ("sweatshirt", "sweat"),
    "스웨트셔츠": ("sweatshirt", "sweat"),
    "티셔츠": ("tshirt", "tee", "tshirts"),
    "반팔티": ("shortsleeve", "tee"),
    "긴팔티": ("longsleeve", "long"),
    "래글런": ("raglan",),
    "레글런": ("raglan",),
    "셔츠": ("shirt", "shirts"),
    "니트": ("knit", "knitwear"),
}


def lexical_match(keyword: str, text: str) -> bool:
    """키워드가 상품명에 어휘적으로 나타나는가.

    한국어 합성어는 그대로 박혀 있는 경우가 많다('...피그먼트 맨투맨 ...').
    토큰이 겹치거나, 키워드가 통째로 들어 있으면 근거로 본다.
    """
    kw_tokens = _tokens(keyword)
    if not kw_tokens:
        return False
    text_tokens = _tokens(text)
    if kw_tokens & text_tokens:
        return True
    flat = _flat(text)
    if any(t in flat for t in kw_tokens if len(t) >= 3):
        return True
    # 한영 표기 대응
    for t in kw_tokens:
        for alias in BILINGUAL.get(t, ()):
            if alias in flat:
                return True
    return False


def match_products(
    conn: sqlite3.Connection, keyword: str, limit: int = MATCH_LIMIT
) -> List[tuple]:
    """(상품명, 유사도, 어휘근거) 목록. 두 경로로 후보를 뽑아 합친다.

    어휘 매칭을 벡터 결과의 필터로만 쓰면, 벡터가 후보에 올리지 못한 것은
    어휘 근거가 있어도 볼 기회가 없다. 실제로 '후드티' 검색 상위에 진짜
    후드 상품이 하나도 안 떴다. 짧은 질의와 긴 상품명은 임베딩 유사도가
    구조적으로 낮기 때문이다.

    그래서 벡터 경로와 어휘 경로가 각각 후보를 내고 합집합을 쓴다.
    """
    vectorstore.init(conn)

    scored: Dict[str, float] = {}
    for h in vectorstore.search(conn, keyword, limit=limit * 3,
                                channel="commerce_rank",
                                min_similarity=MATCH_RECALL_SIMILARITY):
        scored[h.text] = h.similarity

    # 어휘 경로는 원천 데이터에서 직접 읽는다. 벡터 색인에서 가져오면 색인이
    # 낡았을 때 그 낡음을 그대로 물려받아 두 경로를 나눈 의미가 사라진다.
    # 임베딩이 필요 없는 경로이므로 색인에 의존할 이유도 없다.
    names = [r[0] for r in conn.execute(
        "SELECT DISTINCT keyword_raw FROM signal_raw WHERE channel='commerce_rank'")]

    out = []
    for name in set(names) | set(scored):
        lex = lexical_match(keyword, name)
        sim = scored.get(name)
        if lex:
            # 어휘 근거 자체가 정밀도 관문이므로 벡터 점수로 뒤집지 않는다.
            # 여기에 유사도 하한을 걸었더니, 점수가 애매하게 낮은 상품이
            # 점수가 아예 없는 상품보다 불리해지는 모순이 생겼다.
            out.append((name, sim, True))
        elif sim is not None and sim >= MATCH_STRICT_SIMILARITY:
            out.append((name, sim, False))

    out.sort(key=lambda t: (-(t[1] or 0.0), t[0]))
    return out[:limit]


def commerce_signals(
    conn: sqlite3.Connection,
    keyword: str,
    as_of: str,
    window_days: int = RECENT_DAYS + BASE_DAYS,
) -> Optional[CommerceSignal]:
    """후보에 해당하는 실제 상품을 찾아 순위·리뷰 변화를 낸다.

    후보는 검색어이고 커머스 자료는 상품명이라 문자열로는 이어지지 않는다.
    벡터 검색으로 잇는다. 하한선 미만은 버린다. 잘못 이어진 상품의 변동을
    후보의 신호로 읽으면 판정이 오염된다.

    맞는 상품이 없거나 창 안에 커머스 자료가 없으면 None 을 돌려준다.
    크롤링은 소급 수집이 안 되므로 과거 시점 케이스에는 자료가 없는 것이 정상이다.
    """
    cut = date.fromisoformat(as_of[:10])
    start = (cut - timedelta(days=window_days)).isoformat()
    end = cut.isoformat()

    try:
        matches = match_products(conn, keyword)
    except vectorstore.VecExtensionUnavailable:
        return None
    if not matches:
        return None

    names = [m[0] for m in matches]
    placeholders = ",".join("?" for _ in names)
    rows = conn.execute(
        f"""
        SELECT keyword_raw, entity, metric_type, observed_at, metric_value, metadata
        FROM signal_raw
        WHERE channel='commerce_rank' AND keyword_raw IN ({placeholders})
          AND observed_at >= ? AND observed_at < ?
        ORDER BY observed_at
        """, (*names, start, end)).fetchall()
    if not rows:
        return None

    first: Dict[tuple, float] = {}
    last: Dict[tuple, float] = {}
    sold_out = set()
    for r in rows:
        key = (r["keyword_raw"], r["entity"], r["metric_type"])
        first.setdefault(key, r["metric_value"])
        last[key] = r["metric_value"]
        if r["metric_type"] == "rank" and json.loads(r["metadata"] or "{}").get("sold_out"):
            sold_out.add(r["keyword_raw"])

    improved = worsened = 0
    rank_deltas: List[float] = []
    review_total = 0
    grew = 0
    examples: List[str] = []
    for (name, entity, metric), first_v in first.items():
        delta = first_v - last[(name, entity, metric)]
        if metric == "rank":
            # 순위는 숫자가 작을수록 좋다. 양수면 올라간 것.
            rank_deltas.append(delta)
            if delta > 0:
                improved += 1
                if len(examples) < 5:
                    examples.append(f"{name} {int(first_v)}→{int(last[(name, entity, metric)])}위")
            elif delta < 0:
                worsened += 1
        elif metric == "review_count":
            growth = int(-delta)     # 리뷰는 늘어야 좋다
            review_total += max(0, growth)
            if growth > 0:
                grew += 1

    mean_change = statistics.fmean(rank_deltas) if rank_deltas else None
    # 계획서의 반증 신호. 순위는 올랐는데 구매를 거쳐야 쌓이는 리뷰가 안 늘면
    # 광고 노출이나 프로모션 효과를 의심할 근거가 된다.
    contradiction = bool(improved and improved > worsened and grew == 0)

    return CommerceSignal(
        matched_items=len({n for n, _, _ in first}),
        rank_improved=improved,
        rank_worsened=worsened,
        mean_rank_change=mean_change,
        review_growth_total=review_total,
        items_with_review_growth=grew,
        sold_out=len(sold_out),
        contradiction=contradiction,
        examples=examples,
    )


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

    feats.commerce = commerce_signals(conn, keyword, cut.isoformat(),
                                      window_days=window_days)
    if feats.commerce:
        feats.channels["커머스"] = ChannelTrend(
            channel="commerce_rank", entity="(벡터 매칭)",
            n_days=0, coverage=1.0,
            recent_mean=None, base_mean=None,
            change_ratio=None,
            slope=feats.commerce.mean_rank_change,
            last_value=None)
        if feats.commerce.contradiction:
            feats.notes.append(
                "순위는 올랐는데 리뷰 증가가 없다. 광고 노출이나 프로모션 효과를 "
                "의심할 근거다")
    else:
        feats.notes.append(
            "창 안에 커머스 자료가 없다. 크롤링은 소급 수집이 안 되므로 "
            "수집 시작 이전 시점의 케이스에는 붙일 수 없다")

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
