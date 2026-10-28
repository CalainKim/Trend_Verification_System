"""순위 상승이 지속되는지 판정할 케이스를 만든다.

무신사가 겪는 문제는 "갑자기 잘 팔리는데 이유를 모르고, 매진까지 모른다" 이다.
내부적으로 내린 결론은 노이즈 제거, 곧 어떤 것이 진짜 시그널이냐를 가리는 일이다.

원인은 외부에서 관측할 수 없다. 광고 집행과 노출 알고리즘은 쇼핑몰 내부에만
있다. 그래서 원인 대신 수명을 본다. 광고로 올린 순위는 광고가 끝나면 떨어지고,
그 떨어짐은 밖에서도 보인다. 질문을 "왜 올랐나" 에서 "얼마나 버티나" 로 바꾸면
관측 불가능한 문제가 관측 가능한 문제가 된다.

정답을 사람이 정하지 않는 것이 이 모듈의 핵심이다. 역추적 케이스는 연구자가
T_peak 을 지정해야 해서 1건에서 멈춰 있었다. 지속 여부는 자료가 답하므로
케이스가 자동으로 쌓인다.

누수 차단은 함수를 쪼개는 방식으로 강제한다. rise_events 는 관측 구간만 받고
label_events 는 확인 구간만 받는다. 한 함수가 양쪽을 다 보면 특징 계산이
정답을 엿볼 수 있고, 그래도 오류는 나지 않는다.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

#: 상승으로 볼 최소 순위 변화. 랭킹 100위 안에서 10계단은 눈에 띄는 변화다.
MIN_RISE = 10.0

#: 확인 구간에서 상승폭의 이만큼이 남아 있으면 지속으로 본다.
KEEP_RATIO = 0.5

PERSIST, FADE = "persist", "fade"

#: 번들에 함께 싣는 해석의 제한. 모델이 이것을 넘어선 주장을 하면 안 된다.
LIMITATIONS = [
    "순위가 오른 원인은 관측할 수 없다. 광고 집행과 노출 알고리즘은 쇼핑몰 "
    "내부에만 있어 외부에서 볼 수 없다. 원인을 지목하지 말고 관측된 사실과 "
    "배제되는 설명만 쓴다.",
    "리뷰와 좋아요는 플랫폼 내부 지표다. 쇼핑몰 밖의 수요를 직접 재지 않는다.",
    "관측 구간이 짧아 계절성을 분리할 수 없다. 작년 같은 시기와 비교한 자료가 "
    "번들에 없다.",
    "순위는 같은 카테고리 안의 상대 위치다. 판매량의 절대 크기가 아니다.",
]


@dataclass
class Window:
    """기준, 관측, 확인 세 구간. T_cut 이후 자료는 특징에 들어가면 안 된다."""
    base: List[str]
    detect: List[str]
    hold: List[str]

    @property
    def t_cut(self) -> str:
        """판정 기준 시점. 이 날짜까지만 알 수 있었다고 가정한다."""
        return self.detect[-1]


@dataclass
class RiseEvent:
    item_key: str
    name: str
    brand: str
    t_cut: str
    rank_base: float
    rank_detect: float
    rise: float
    review_delta: float
    heart_delta: float
    sale_delta: float
    is_new: bool
    sold_out: bool
    brand_risers: int = 1          # 같은 창에서 동시 상승한 같은 브랜드 상품 수

    def evidence(self, w: "Window") -> List[dict]:
        """검증 파트가 인용할 근거 항목.

        review.py 의 validate_result 가 모델의 인용 ID 를 이 목록에 있는 id 로
        검증한다. id 가 없으면 모델이 무엇을 보고 말했는지 확인할 수 없다.
        """
        base, det = f"{w.base[0]}~{w.base[-1]}", f"{w.detect[0]}~{w.detect[-1]}"
        out = [
            {"id": "rank_change", "channel": "commerce_rank",
             "observation": f"순위 평균이 {base} 구간 {self.rank_base:.1f}위에서 "
                            f"{det} 구간 {self.rank_detect:.1f}위로 "
                            f"{self.rise:.1f}계단 올랐다"},
            {"id": "review_change", "channel": "commerce_rank",
             "observation": f"같은 기간 리뷰 수가 {self.review_delta:+.1f}건 변했다. "
                            f"리뷰는 구매를 거쳐야 쌓이므로 조작 여지가 적다"},
            {"id": "heart_change", "channel": "commerce_rank",
             "observation": f"좋아요가 {self.heart_delta:+.1f} 변했다. "
                            f"구매 없이도 늘 수 있는 지표다"},
            {"id": "sale_change", "channel": "commerce_rank",
             "observation": f"할인율이 {self.sale_delta:+.1f}%p 변했다. "
                            f"할인이 늘었다면 순위 상승의 대체 설명이 된다"},
            {"id": "item_flags", "channel": "commerce_rank",
             "observation": f"신상품 표시 {self.is_new}, 품절 {self.sold_out}"},
            {"id": "brand_context", "channel": "commerce_rank",
             "observation": f"같은 창에서 브랜드 '{self.brand}' 의 상품 "
                            f"{self.brand_risers}개가 함께 올랐다"},
        ]
        return out

    def features(self) -> Dict[str, object]:
        """검증 단계로 넘길 특징. T_cut 이전 자료만 들어 있다."""
        return {
            "rank_base": round(self.rank_base, 2),
            "rank_at_cut": round(self.rank_detect, 2),
            "rank_rise": round(self.rise, 2),
            "review_delta": round(self.review_delta, 2),
            "heart_delta": round(self.heart_delta, 2),
            "sale_percent_delta": round(self.sale_delta, 2),
            "is_new": self.is_new,
            "sold_out": self.sold_out,
            "brand_simultaneous_risers": self.brand_risers,
        }


def load_series(
    conn: sqlite3.Connection, channel: str = "commerce_rank"
) -> Dict[str, Dict[str, dict]]:
    """상품별 일자별 지표. 랭킹 entity 의 카테고리 접미사는 떼어 묶는다."""
    out: Dict[str, Dict[str, dict]] = {}
    rows = conn.execute(
        """
        SELECT observed_at, entity, keyword_raw, metric_type, metric_value, metadata
        FROM signal_raw WHERE channel = ?
          AND metric_type IN ('rank', 'review_count', 'heart_count')
        ORDER BY observed_at
        """, (channel,)).fetchall()
    for r in rows:
        key = r["entity"].split("@", 1)[0]
        day = r["observed_at"][:10]
        slot = out.setdefault(key, {}).setdefault(day, {})
        slot[r["metric_type"]] = r["metric_value"]
        if r["metric_type"] == "rank":
            meta = json.loads(r["metadata"] or "{}")
            slot["name"] = r["keyword_raw"]
            slot["brand"] = meta.get("brand_kor") or meta.get("brand_eng") or ""
            slot["sale"] = meta.get("sale_percent") or 0.0
            slot["is_new"] = bool(meta.get("is_new"))
            slot["sold_out"] = bool(meta.get("sold_out"))
    return out


def observed_days(series: Dict[str, Dict[str, dict]]) -> List[str]:
    return sorted({d for v in series.values() for d in v})


def windows(days: Sequence[str], base: int, detect: int, hold: int,
            step: int = 1) -> List[Window]:
    """창을 밀면서 구간을 만든다.

    step 을 1 로 두면 창이 겹친다. 겹친 창에서 나온 케이스는 서로 독립이
    아니므로 표본 수를 그대로 통계에 쓰면 안 된다. 독립 표본만 필요하면
    step 을 base+detect+hold 로 준다.
    """
    span = base + detect + hold
    out = []
    for i in range(0, len(days) - span + 1, step):
        out.append(Window(base=list(days[i:i + base]),
                          detect=list(days[i + base:i + base + detect]),
                          hold=list(days[i + base + detect:i + span])))
    return out


def _avg(item: Dict[str, dict], days: Sequence[str], key: str) -> Optional[float]:
    vals = [item[d][key] for d in days if d in item and key in item[d]]
    return sum(vals) / len(vals) if vals else None


def _latest(item: Dict[str, dict], days: Sequence[str], key: str, default=None):
    for d in reversed(days):
        if d in item and key in item[d]:
            return item[d][key]
    return default


def rise_events(series: Dict[str, Dict[str, dict]], w: Window,
                min_rise: float = MIN_RISE) -> List[RiseEvent]:
    """관측 구간에서 순위가 오른 상품. 확인 구간은 쳐다보지 않는다.

    이 함수에 w.hold 를 쓰는 코드를 넣으면 안 된다. 특징이 정답을 보게 되고
    모델 성적이 실제보다 좋게 나오는데 오류는 나지 않아 발견하기 어렵다.
    """
    seen = w.base + w.detect
    found: List[RiseEvent] = []
    for key, item in series.items():
        rb, rd = _avg(item, w.base, "rank"), _avg(item, w.detect, "rank")
        if rb is None or rd is None:
            continue
        rise = rb - rd                      # 순위는 숫자가 작아질수록 상승이다
        if rise < min_rise:
            continue
        rev_b, rev_d = _avg(item, w.base, "review_count"), _avg(item, w.detect, "review_count")
        hb, hd = _avg(item, w.base, "heart_count"), _avg(item, w.detect, "heart_count")
        sb, sd = _avg(item, w.base, "sale"), _avg(item, w.detect, "sale")
        found.append(RiseEvent(
            item_key=key,
            name=_latest(item, seen, "name", "") or "",
            brand=_latest(item, seen, "brand", "") or "",
            t_cut=w.t_cut,
            rank_base=rb, rank_detect=rd, rise=rise,
            review_delta=(rev_d - rev_b) if None not in (rev_b, rev_d) else 0.0,
            heart_delta=(hd - hb) if None not in (hb, hd) else 0.0,
            sale_delta=(sd - sb) if None not in (sb, sd) else 0.0,
            is_new=bool(_latest(item, seen, "is_new", False)),
            sold_out=bool(_latest(item, seen, "sold_out", False)),
        ))

    # 같은 브랜드가 한 창에서 몇 개나 함께 올랐는지. 브랜드 단위 효과를
    # 상품 단위 신호와 구분하려면 필요하다.
    counts: Dict[str, int] = {}
    for e in found:
        if e.brand:
            counts[e.brand] = counts.get(e.brand, 0) + 1
    for e in found:
        e.brand_risers = counts.get(e.brand, 1)
    return found


def label_events(series: Dict[str, Dict[str, dict]], w: Window,
                 events: Sequence[RiseEvent],
                 keep_ratio: float = KEEP_RATIO) -> Dict[str, str]:
    """확인 구간을 보고 지속 여부를 정한다. 정답은 여기서만 만들어진다."""
    out: Dict[str, str] = {}
    for e in events:
        item = series[e.item_key]
        rh = _avg(item, w.hold, "rank")
        if rh is None:
            continue                       # 확인 구간에 자료가 없으면 채점 불가
        kept = e.rank_base - rh
        out[e.item_key] = PERSIST if kept >= e.rise * keep_ratio else FADE
    return out


# --------------------------------------------------------------- 지수 시계열
#
# 커머스 랭킹은 수집을 시작한 날부터만 있다. 29일로는 독립 표본이 하나뿐이라
# 통계적 주장을 할 수 없었다. 검색 지수는 과거를 소급 조회할 수 있어 같은
# 질문을 몇 년치로 물을 수 있다.
#
# 묻는 것은 같다. 올랐는가가 아니라 오른 것이 버티는가이다. 다만 순위는
# 계단 수로 재고 지수는 비율로 잰다. 지수는 요청 창 안에서 최댓값이 100 이
# 되도록 정규화된 상대값이라 차이의 절대 크기에 뜻이 없기 때문이다.

#: 기준 구간 대비 이 비율 이상 오르면 상승으로 본다.
MIN_RISE_RATIO = 1.2


@dataclass
class IndexRiseEvent:
    key: str                     # 키워드
    entity: str
    t_cut: str
    base_mean: float
    detect_mean: float
    rise_ratio: float
    yoy_ratio: Optional[float]   # 작년 같은 기간 대비. 계절성 반증용
    coverage: float              # 창 안에서 실제로 관측된 비율

    def features(self) -> Dict[str, object]:
        return {
            "base_mean": round(self.base_mean, 2),
            "detect_mean": round(self.detect_mean, 2),
            "rise_ratio": round(self.rise_ratio, 3),
            "rise_pct": round((self.rise_ratio - 1) * 100, 1),
            "yoy_ratio": round(self.yoy_ratio, 3) if self.yoy_ratio is not None else None,
            "coverage": round(self.coverage, 3),
        }

    def evidence(self, w: "Window", channel: str) -> List[dict]:
        out = [
            {"id": "index_change", "channel": channel,
             "observation": f"지수 평균이 기준 구간 {self.base_mean:.1f} 에서 "
                            f"관측 구간 {self.detect_mean:.1f} 로 "
                            f"{(self.rise_ratio - 1) * 100:+.1f}% 변했다"},
            {"id": "coverage", "channel": channel,
             "observation": f"창 안에서 관측된 비율이 {self.coverage:.0%} 다. "
                            f"결측이 많으면 추세를 읽을 수 없다"},
        ]
        if self.yoy_ratio is not None:
            out.append({
                "id": "seasonality", "channel": channel,
                "observation": f"작년 같은 기간 대비 {self.yoy_ratio:.2f} 배다. "
                               f"1 에 가까우면 해마다 반복되는 움직임이고, "
                               f"그렇다면 계절성으로 설명된다"})
        else:
            out.append({
                "id": "seasonality", "channel": channel,
                "observation": "작년 같은 기간 자료가 없어 계절성을 확인할 수 없다"})
        return out


def load_index_series(conn: sqlite3.Connection, channel: str, entity: str = "",
                      metric_type: str = "search_index",
                      require_single_window: bool = True
                      ) -> Dict[str, Dict[str, float]]:
    """키워드별 지수 시계열.

    정규화 창이 섞인 키워드는 빼는 것이 기본이다. 구글 트렌드와 네이버 두
    API 는 요청 창 안에서 최댓값을 100 으로 맞추므로, 창이 다른 값을 한
    시계열로 이으면 이음새에 없던 계단이 생긴다. 그 계단을 상승으로 읽으면
    케이스가 통째로 거짓이 된다.
    """
    rows = conn.execute(
        """
        SELECT keyword_raw, observed_at, metric_value,
               json_extract(metadata,'$.query_start') || ' ~ '
            || json_extract(metadata,'$.query_end') w
        FROM signal_raw
        WHERE channel=? AND entity=? AND metric_type=?
        ORDER BY keyword_raw, observed_at
        """, (channel, entity, metric_type)).fetchall()

    out: Dict[str, Dict[str, float]] = {}
    windows: Dict[str, set] = {}
    for r in rows:
        kw = r["keyword_raw"]
        out.setdefault(kw, {})[r["observed_at"][:10]] = r["metric_value"]
        if r["w"]:
            windows.setdefault(kw, set()).add(r["w"])
    if require_single_window:
        for kw, ws in windows.items():
            if len(ws) > 1:
                out.pop(kw, None)
    return out


def _mean(item: Dict[str, float], days: Sequence[str]) -> Tuple[Optional[float], float]:
    vals = [item[d] for d in days if d in item]
    if not vals:
        return None, 0.0
    return sum(vals) / len(vals), len(vals) / len(days)


def yoy_ratio(item: Dict[str, float], days: Sequence[str],
              years_back: int = 1, tol_days: int = 10) -> Optional[float]:
    """작년 같은 기간 대비 비율.

    계절성 반증에 쓴다. 해마다 같은 시기에 오르는 것이라면 이 값이 1 에
    가깝고, 올해만 오른 것이라면 1 보다 크다.

    주간 자료라 날짜가 정확히 맞지 않으므로 tol_days 안에서 가장 가까운
    관측을 쓴다. 맞는 날이 없으면 None 을 돌려준다. 억지로 메우면 계절성이
    없다고 잘못 읽는다.
    """
    from datetime import date, timedelta
    cur, past = [], []
    keys = sorted(item)
    for d in days:
        if d not in item:
            continue
        target = (date.fromisoformat(d) - timedelta(days=365 * years_back))
        best = min(keys, key=lambda k: abs((date.fromisoformat(k) - target).days))
        if abs((date.fromisoformat(best) - target).days) > tol_days:
            continue
        cur.append(item[d])
        past.append(item[best])
    if len(cur) < 2 or sum(past) == 0:
        return None
    return (sum(cur) / len(cur)) / (sum(past) / len(past))


def index_rise_events(series: Dict[str, Dict[str, float]], w: Window,
                      min_ratio: float = MIN_RISE_RATIO,
                      min_coverage: float = 0.5,
                      entity: str = "") -> List[IndexRiseEvent]:
    """관측 구간에서 지수가 오른 키워드. 확인 구간은 쳐다보지 않는다."""
    found = []
    for kw, item in series.items():
        bm, bc = _mean(item, w.base)
        dm, dc = _mean(item, w.detect)
        if bm is None or dm is None or bm <= 0:
            continue
        cov = min(bc, dc)
        if cov < min_coverage:
            continue                  # 결측이 많으면 추세를 읽을 수 없다
        ratio = dm / bm
        if ratio < min_ratio:
            continue
        found.append(IndexRiseEvent(
            key=kw, entity=entity, t_cut=w.t_cut,
            base_mean=bm, detect_mean=dm, rise_ratio=ratio,
            yoy_ratio=yoy_ratio(item, w.base + w.detect), coverage=cov))
    return found


def label_index_events(series: Dict[str, Dict[str, float]], w: Window,
                       events: Sequence[IndexRiseEvent],
                       keep_ratio: float = KEEP_RATIO) -> Dict[str, str]:
    """확인 구간에서 상승분의 절반이 남았는지. 정답은 여기서만 만들어진다."""
    out: Dict[str, str] = {}
    for e in events:
        hm, hc = _mean(series[e.key], w.hold)
        if hm is None or hc < 0.5:
            continue
        kept = hm / e.base_mean
        threshold = 1 + (e.rise_ratio - 1) * keep_ratio
        out[e.key] = PERSIST if kept >= threshold else FADE
    return out


def base_rate(labels: Sequence[str]) -> Optional[float]:
    """아무 생각 없이 '지속' 이라고 찍었을 때의 정확도.

    모델 성적은 이 값과 비교해야 뜻이 생긴다. 기저율을 빼고 정확도만 보고하면
    찍은 것과 같은 점수를 성과로 읽게 된다.
    """
    if not labels:
        return None
    return sum(1 for x in labels if x == PERSIST) / len(labels)
