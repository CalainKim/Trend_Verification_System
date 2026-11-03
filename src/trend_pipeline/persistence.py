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
#: 그날 TOP100 목록에 없던 상품의 순위로 쓰는 값. 목록이 100위까지이므로 밖에
#: 있었다는 것은 "101위보다 나쁘다" 는 뜻이고, 101 은 그 경계값이다.
#:
#: 전에는 없는 날을 그냥 빼고 평균했다. 그러면 이레 중 하루만 목록에 있던
#: 상품이 그 하루 순위로 평균을 내서 크게 오른 것으로 잡힌다. 오른 것이 아니라
#: 평균을 낸 날이 하루인 것이다. 61건 가운데 19건이 이레 중 이틀 이하였고,
#: 하나는 하루 7위로 "42계단 올랐다" 가 됐다.
#:
#: 커버리지 문턱으로 거르는 방법도 재 봤으나 더 나빴다. 0.5 로 자르면 80건이
#: 29건으로 줄고 기저율이 51.2% 에서 65.5% 로 뛴다. 목록에 꾸준히 있던 상품만
#: 남으니 버틸 것들만 고른 꼴이다. 경계값으로 채우면 50건이 남고 기저율은
#: 60.0% 이며, 하루만 있던 18건 가운데 17건이 상승 문턱에서 자연히 떨어진다.
#: 거르는 것이 아니라 제대로 재니 상승이 아니었던 것이다.
#:
#: 101 은 실제보다 후하다. 밖에 있던 상품이 300위였을 수도 있다. 그 방향의
#: 오차는 상승폭을 작게 보이게 하므로 안전한 쪽이다.
OUT_OF_LIST_RANK = 101.0

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
    # 기준 구간과 관측 구간의 일별 순위. 구간 평균만 주면 꾸준히 오른 것과
    # 하루만 튄 것이 같은 숫자가 된다. 둘은 이후 유지 여부가 다를 수 있는데,
    # 모델이 구분할 방법이 없으면 판단을 보류할 수밖에 없다.
    #
    # None 은 그날 수집한 상위 100 위 목록에 없었다는 뜻이다. 수집이 없던 날이
    # 아니다. 창은 observed_days 로 고른 날만 쓰므로 수집이 없던 날은 애초에
    # 창에 못 들어온다. 이걸 "결측" 이라고 적어 보내는 바람에 모델이 자료 없음
    # 으로 읽고 판단을 보류했다. 기권 37건이 든 이유 가운데 광고 다음으로 많았다.
    #
    # "TOP100 밖으로 떨어졌다" 라고 단정하지는 않는다. 랭킹 호출이 100 개를
    # 다 주지 못하고 돌아오는 일이 드물게 있다. 수집 실행 126 건 가운데 4 건이
    # 97 개에서 99 개를 받았다(2026-09-06, 09-08, 10-02, 10-27). 그 실행에서는
    # 실제로 순위 안에 있던 상품 하나가 목록에서 빠진다. 그래서 문장은 "그날
    # 수집한 목록에 없었다" 까지만 말한다. 이것은 어느 쪽이든 참이다.
    rank_daily: Tuple[Optional[float], ...] = ()
    #: 구간 평균이 며칠을 쓴 것인지. 1.0 이면 창의 모든 날에 목록 안에 있었다.
    coverage_base: float = 1.0
    coverage_detect: float = 1.0
    # 이 상품의 속성이 작년 같은 시기에도 올랐는지. 계절성 반증용이다. 모델이
    # 판정을 보류한 이유로 가장 많이 든 항목이 이것이었다. 커머스 수집은 37일뿐
    # 이라 작년이 없지만, 속성 키워드의 검색 지수에는 5년치가 있다.
    seasonality: Optional[dict] = None

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
        if self.rank_daily:
            days = list(w.base) + list(w.detect)
            pairs = ", ".join(
                f"{d[5:]} {'TOP100 밖' if v is None else f'{v:.0f}위'}"
                for d, v in zip(days, self.rank_daily))
            note = (f"일별 순위는 {pairs} 다. 여기 적힌 날은 모두 수집이 돌았던 "
                    f"날이고, 'TOP100 밖' 은 그날 수집한 상위 100 위 목록에 이 "
                    f"상품이 없었다는 뜻이다. 수집이 걸러진 결측과는 다르다. "
                    f"구간 평균만으로는 꾸준히 오른 것과 하루만 튄 것을 구분할 "
                    f"수 없다")
            note += (f". 목록에 없던 날은 {OUT_OF_LIST_RANK:.0f} 위로 쳐서 평균에 "
                     f"넣었다. 목록이 100 위까지이므로 밖에 있었다는 것은 그보다 "
                     f"나쁘다는 뜻이고, 빼고 평균하면 하루만 높았던 상품이 크게 "
                     f"오른 것으로 보인다. 목록 안에 있던 날은 기준 구간 "
                     f"{self.coverage_base:.0%}, 관측 구간 {self.coverage_detect:.0%} 다")
            gaps = _calendar_gaps(days)
            if gaps:
                note += (f". 다만 {', '.join(gaps)} 은 수집 자체가 없어 "
                         f"그날의 순위는 알 수 없다")
            out.append({"id": "rank_daily", "channel": "commerce_rank",
                        "observation": note})
        s = self.seasonality
        if s and s.get("yoy") is not None:
            out.append({
                "id": "seasonality", "channel": "gtrends",
                "observation": (
                    f"이 상품의 속성 '{s['attribute']}' 의 한국 검색 지수는 "
                    f"작년 같은 시기 대비 {s['yoy']:.2f} 배다. 1 에 가까우면 "
                    f"해마다 같은 시기에 오르는 계절 움직임이고, 1 보다 크게 "
                    f"높으면 올해만 오른 것이다. 상품 순위가 아니라 속성 검색의 "
                    f"계절성이므로 간접 근거다")})
        elif s and s.get("attribute"):
            out.append({
                "id": "seasonality", "channel": "gtrends",
                "observation": (
                    f"속성 '{s['attribute']}' 는 검색 지수가 있으나 작년 같은 "
                    f"시기의 관측이 없어 계절성을 재지 못했다")})
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


def _calendar_gaps(days: Sequence[str]) -> List[str]:
    """창에 적힌 날들 사이에 수집이 통째로 없던 날을 찾는다.

    창은 수집이 있었던 날만 골라 이어 붙인 것이라, 10-16 다음이 10-18 일 수
    있다. 그 사이 10-17 은 그 상품이 밖에 있던 것이 아니라 아무도 수집하지
    않은 날이다. 둘을 한 단어로 적으면 모델이 구분하지 못한다.
    """
    from datetime import date, timedelta

    out: List[str] = []
    for a, b in zip(days, days[1:]):
        d, end = date.fromisoformat(a) + timedelta(days=1), date.fromisoformat(b)
        while d < end:
            out.append(d.isoformat()[5:])
            d += timedelta(days=1)
    return out


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
    """있는 날만 평균한다. 몇 날을 썼는지는 _avg_cov 로 따로 받는다."""
    vals = [item[d][key] for d in days if d in item and key in item[d]]
    return sum(vals) / len(vals) if vals else None


def _avg_rank(item: Dict[str, dict],
              days: Sequence[str]) -> Tuple[float, float]:
    """순위의 구간 평균과, 그 구간에서 목록 안에 있었던 날의 비율.

    목록에 없던 날은 빼지 않고 OUT_OF_LIST_RANK 로 채운다. 빼면 남은 날만으로
    평균이 나서 하루짜리 반짝 진입이 큰 상승으로 보인다. 창은 수집이 있었던
    날로만 만들므로 없는 날은 자료가 없는 것이 아니라 밖에 있었던 것이다.
    """
    vals = [(item.get(d) or {}).get("rank") for d in days]
    seen = sum(1 for v in vals if v is not None)
    filled = [OUT_OF_LIST_RANK if v is None else v for v in vals]
    return sum(filled) / len(filled), seen / len(days)


def _latest(item: Dict[str, dict], days: Sequence[str], key: str, default=None):
    for d in reversed(days):
        if d in item and key in item[d]:
            return item[d][key]
    return default


def rise_events(series: Dict[str, Dict[str, dict]], w: Window,
                min_rise: float = MIN_RISE,
                seasonality: Optional[Dict[str, dict]] = None) -> List[RiseEvent]:
    """관측 구간에서 순위가 오른 상품. 확인 구간은 쳐다보지 않는다.

    이 함수에 w.hold 를 쓰는 코드를 넣으면 안 된다. 특징이 정답을 보게 되고
    모델 성적이 실제보다 좋게 나오는데 오류는 나지 않아 발견하기 어렵다.
    """
    seen = w.base + w.detect
    found: List[RiseEvent] = []
    for key, item in series.items():
        rb, cb = _avg_rank(item, w.base)
        rd, cd = _avg_rank(item, w.detect)
        if not cb and not cd:
            continue                        # 두 구간 모두 목록에 없던 상품
        rise = rb - rd                      # 순위는 숫자가 작아질수록 상승이다
        if rise < min_rise:
            continue
        rev_b, rev_d = _avg(item, w.base, "review_count"), _avg(item, w.detect, "review_count")
        hb, hd = _avg(item, w.base, "heart_count"), _avg(item, w.detect, "heart_count")
        sb, sd = _avg(item, w.base, "sale"), _avg(item, w.detect, "sale")
        daily = tuple((item.get(d) or {}).get("rank") for d in
                      list(w.base) + list(w.detect))
        found.append(RiseEvent(
            item_key=key,
            name=_latest(item, seen, "name", "") or "",
            brand=_latest(item, seen, "brand", "") or "",
            t_cut=w.t_cut,
            rank_base=rb, rank_detect=rd, rise=rise,
            review_delta=(rev_d - rev_b) if None not in (rev_b, rev_d) else 0.0,
            heart_delta=(hd - hb) if None not in (hb, hd) else 0.0,
            sale_delta=(sd - sb) if None not in (sb, sd) else 0.0,
            rank_daily=daily,
            coverage_base=cb, coverage_detect=cd,
            seasonality=(seasonality or {}).get(key),
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
        # 확인 구간 내내 목록에 없으면 rh 가 경계값이 되어 자연히 fade 가
        # 된다. 전에는 _avg 가 None 을 돌려줬고 그것을 채점 불가로 버렸다.
        # 가장 확실하게 버티지 못한 것들이 정답에서 빠져 기저율이 살아남은
        # 쪽으로 올라갔다. 실제로 80건 중 18건이 그렇게 빠졌다.
        rh, _ = _avg_rank(item, w.hold)
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
    key: str                     # 키워드와 entity 를 합친 시계열 키
    keyword: str
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


#: 시계열 키를 만들 때 키워드와 entity 를 잇는 구분자.
#: 키워드에 '@' 가 들어가지 않으므로 되돌릴 수 있다.
SERIES_SEP = "@"


def series_key(keyword: str, entity: str) -> str:
    return f"{keyword}{SERIES_SEP}{entity}" if entity else keyword


def split_series_key(key: str) -> Tuple[str, str]:
    kw, _, ent = key.partition(SERIES_SEP)
    return kw, ent


def load_index_series(conn: sqlite3.Connection, channel: str,
                      entities: Sequence[str] = ("",),
                      metric_type: str = "search_index",
                      require_single_window: bool = True
                      ) -> Dict[str, Dict[str, float]]:
    """키워드와 entity 조합별 지수 시계열.

    entity 를 여러 개 받으면 조합마다 별도 시계열이 된다. 같은 키워드라도
    지역이 다르면 다른 사건이기 때문이다. '헨리넥' 한국 검색의 상승과
    'henley shirt' 미국 검색의 상승은 각각 세는 것이 맞다. 다만 같은 유행이
    양쪽에 걸칠 수 있으므로 완전히 독립은 아니고, 그 사실을 성적표에 남긴다.

    정규화 창이 섞인 시계열은 빼는 것이 기본이다. 구글 트렌드와 네이버 두
    API 는 요청 창 안에서 최댓값을 100 으로 맞추므로, 창이 다른 값을 한
    시계열로 이으면 이음새에 없던 계단이 생긴다. 그 계단을 상승으로 읽으면
    케이스가 통째로 거짓이 된다.
    """
    if isinstance(entities, str):
        entities = (entities,)
    out: Dict[str, Dict[str, float]] = {}
    windows: Dict[str, set] = {}
    for entity in entities:
        rows = conn.execute(
            """
            SELECT keyword_raw, observed_at, metric_value,
                   json_extract(metadata,'$.query_start') || ' ~ '
                || json_extract(metadata,'$.query_end') w
            FROM signal_raw
            WHERE channel=? AND entity=? AND metric_type=?
            ORDER BY keyword_raw, observed_at
            """, (channel, entity, metric_type)).fetchall()
        for r in rows:
            key = series_key(r["keyword_raw"], entity)
            out.setdefault(key, {})[r["observed_at"][:10]] = r["metric_value"]
            if r["w"]:
                windows.setdefault(key, set()).add(r["w"])
    if require_single_window:
        for key, ws in windows.items():
            if len(ws) > 1:
                out.pop(key, None)
    return out


def _mean(item: Dict[str, float], days: Sequence[str]) -> Tuple[Optional[float], float]:
    vals = [item[d] for d in days if d in item]
    if not vals:
        return None, 0.0
    return sum(vals) / len(vals), len(vals) / len(days)


def window_yoy(item: Dict[str, float], days: Sequence[str],
               years_back: int = 1, pad_days: int = 14) -> Optional[float]:
    """날짜 구간으로 맞추는 작년 대비 비율.

    yoy_ratio 는 양쪽이 같은 격자일 때 쓴다. 커머스 창은 일별이고 구글 트렌드는
    주별이라 날짜가 겹치지 않아 그 함수로는 전부 빗나간다. 여기서는 구간을
    범위로 보고, 그 범위 안이나 앞쪽 가까이에 있는 주별 관측을 모아 평균을 낸다.

    패딩은 뒤로는 붙이지 않는다. 부르는 쪽이 days 에 관측 구간을 주므로 뒤쪽
    패딩은 곧 확인 구간이고, 그러면 t_cut 이후 자료가 특징에 섞인다. 처음에는
    앞뒤로 7일씩 붙여서 실제로 그렇게 됐다. 계절성 근거가 붙은 48건 가운데
    47건이 확인 구간의 주간 관측 한 점을 평균에 넣고 있었다. 지금은 같은 길이를
    앞쪽으로만 가져간다. 구간 길이가 같으므로 들어오는 주간 관측 수는 거의
    같고, 작년 쪽도 똑같이 앞으로만 늘어나므로 비율의 뜻이 변하지 않는다.
    """
    from datetime import date, timedelta

    def mean_in(lo: date, hi: date) -> Optional[float]:
        vals = [v for k, v in item.items()
                if lo - timedelta(days=pad_days) <= date.fromisoformat(k) <= hi]
        return sum(vals) / len(vals) if vals else None

    lo, hi = date.fromisoformat(days[0]), date.fromisoformat(days[-1])
    back = timedelta(days=365 * years_back)
    now, then = mean_in(lo, hi), mean_in(lo - back, hi - back)
    if now is None or not then:
        return None
    return now / then


def commerce_seasonality(conn: sqlite3.Connection,
                         series: Dict[str, Dict[str, dict]],
                         w: Window, attrs, colors,
                         geo: str = "geo=KR") -> Dict[str, dict]:
    """상품마다 그 속성의 검색 지수 계절성을 붙인다.

    커머스 수집은 37일뿐이라 작년을 볼 수 없다. 속성 키워드의 검색 지수에는
    5년치가 있으므로 그걸 간접 근거로 쓴다. 상품 순위의 계절성이 아니라 속성
    검색의 계절성이라는 점을 근거 문장에 적어 둔다.

    관측 구간까지만 본다. 확인 구간을 넣으면 정답이 새어 나간다.
    """
    index = load_index_series(conn, "gtrends", entities=(geo,))
    by_kw = {split_series_key(k)[0]: v for k, v in index.items()}
    out: Dict[str, dict] = {}
    for key, item in series.items():
        name = _latest(item, list(w.base) + list(w.detect), "name", "") or ""
        if not name:
            continue
        for a in attrs_of(name, attrs, colors):
            s = by_kw.get(a)
            if s is None:
                continue
            out[key] = {"attribute": a, "yoy": window_yoy(s, w.detect)}
            break
    return out


def attrs_of(name: str, attrs, colors) -> List[str]:
    """상품명에서 뽑은 속성 이름. 사전 쪽 구현을 그대로 쓴다."""
    import sys
    from pathlib import Path as _P
    sys.path.insert(0, str(_P(__file__).resolve().parents[2] / "scripts"))
    import extract_attributes as ea
    return [a["canonical"] for a in ea.extract(name, attrs, colors)]


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
                      min_coverage: float = 0.5) -> List[IndexRiseEvent]:
    """관측 구간에서 지수가 오른 시계열. 확인 구간은 쳐다보지 않는다."""
    found = []
    for key, item in series.items():
        kw, entity = split_series_key(key)
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
            key=key, keyword=kw, entity=entity, t_cut=w.t_cut,
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
