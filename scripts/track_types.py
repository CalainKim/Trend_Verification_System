#!/usr/bin/env python3
"""유형이 여러 주에 걸쳐 어떻게 변하는지 따라간다.

과제의 세 단계 가운데 "계속해서 지켜본다" 에 해당한다. 한 주의 판정만 보면
반짝 오른 것과 몇 주째 버티는 것을 구분할 수 없다.

    ./scripts/track_types.py                주간 궤적 출력
    ./scripts/track_types.py --weeks 5
    ./scripts/track_types.py --json out.json

판정 기준은 화면(Trend Monitor)과 같은 식을 쓴다. 두 곳이 다른 기준을 쓰면
같은 유형을 두고 화면과 보고서가 다른 말을 한다.

    오른 상품 0건                                    신호 없음
    3건 이상, 브랜드 3곳 이상, 1위 브랜드 점유 50% 이하   트렌드 후보
    2건 이상, 1위 브랜드 점유 50% 초과                 브랜드 단독
    나머지                                          관찰
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from export_frontend import MIN_RISE, ranks_on, snapshot_days, type_of  # noqa: E402
from trend_pipeline import storage  # noqa: E402

NONE, CAND, SOLO, WATCH = "신호 없음", "트렌드 후보", "브랜드 단독", "관찰"
ORDER = [CAND, WATCH, SOLO, NONE]
MARK = {CAND: "후보", WATCH: "관찰", SOLO: "단독", NONE: "없음"}

# 한 주 판정이 큰 카테고리를 그냥 통과시킨다. 티셔츠는 TOP100 에 마흔 개가
# 넘게 있어서 매주 서넛은 오르고, 그래서 늘 후보로 찍힌다. 후드가 다섯 건에서
# 스무 건이 된 것과 구분되지 않는다. 수준이 아니라 방향을 함께 봐야 한다.
GROW, FLAT, SHRINK = "확대", "유지", "축소"
TREND_SLOPE = 0.15     # 주당 상승 비율이 이보다 크면 확대로 본다


def weekly_chain(days: List[str], weeks: int, span: int = 7,
                 slack: int = 3) -> List[str]:
    """7일 간격에 가장 가까운 수집일을 이어 붙인다.

    29CM 수집이 하루씩 빠진 날이 있어 고정 간격으로는 빈 날을 집는다. 간격이
    slack 일보다 더 벌어지면 거기서 끊는다. 억지로 이으면 2주 간격을 1주로
    읽어 궤적이 거짓말을 한다.
    """
    if not days:
        return []
    chain = [days[-1]]
    cur = date.fromisoformat(days[-1])
    while len(chain) < weeks + 1:
        target = cur - timedelta(days=span)
        earlier = [d for d in days if d < chain[-1]]
        if not earlier:
            break
        nearest = min(earlier, key=lambda d: abs((date.fromisoformat(d) - target).days))
        if abs((date.fromisoformat(nearest) - target).days) > slack:
            break
        chain.append(nearest)
        cur = date.fromisoformat(nearest)
    return chain[::-1]


def brand_mix(risen: List[dict]) -> dict:
    """브랜드 쏠림. 판정이 실제로 보는 값이다.

    브랜드가 몇 곳인지보다 1위가 얼마나 가져가는지가 중요하다. 스물여덟 곳이어도
    한 곳이 절반을 넘으면 브랜드 단독이다. 개수만 보여 주면 판정 근거가 화면에
    안 드러난다.
    """
    if not risen:
        return {"n_brand": 0, "top": None, "top_n": 0, "top_share": 0.0}
    c = Counter(p["brand"] for p in risen)
    name, n = c.most_common(1)[0]
    return {"n_brand": len(c), "top": name, "top_n": n,
            "top_share": round(n / len(risen), 3)}


def verdict(risen: List[dict]) -> str:
    """화면과 같은 판정식."""
    if not risen:
        return NONE
    mix = brand_mix(risen)
    if len(risen) >= 3 and mix["n_brand"] >= 3 and mix["top_share"] <= 0.5:
        return CAND
    if len(risen) >= 2 and mix["top_share"] > 0.5:
        return SOLO
    return WATCH


def week_snapshot(conn, prev_day: str, day: str) -> Dict[str, dict]:
    """그 주의 유형별 상태. 오른 것은 직전 주와 견줘 정한다."""
    prev, cur = ranks_on(conn, prev_day), ranks_on(conn, day)
    by_type: Dict[str, List[dict]] = {}
    risen_by_type: Dict[str, List[dict]] = {}
    for entity, p in cur.items():
        t = type_of(p["name"])
        by_type.setdefault(t, []).append(p)
        was = prev.get(entity)
        if was is None or was["rank"] - p["rank"] >= MIN_RISE:
            risen_by_type.setdefault(t, []).append(p)
    out = {}
    for t, prods in by_type.items():
        risen = risen_by_type.get(t, [])
        mix = brand_mix(risen)
        out[t] = {
            "n_top": len(prods),
            "n_rise": len(risen),
            "n_brand": mix["n_brand"],
            "top_brand": mix["top"],
            "top_brand_n": mix["top_n"],
            "top_brand_share": mix["top_share"],
            "verdict": verdict(risen),
        }
    return out


def direction(tops: List[float]) -> tuple:
    """유형이 TOP100 에서 차지하는 자리가 주마다 어느 쪽으로 가는지.

    오른 상품 수를 TOP100 안 개수로 나누면 안 된다. 후드는 여덟 개에서 스물여덟
    개로 늘면서 오른 수도 같이 늘어, 비율로는 제자리처럼 보인다. 유행하는 유형은
    TOP100 안에 들어오는 상품 자체가 늘어나므로 그 개수를 본다.

    앞 절반과 뒤 절반의 평균을 견준다. 다섯 주로 기울기를 재면 한 주만 튀어도
    부호가 바뀌어서, 구간 평균이 더 버틴다.
    """
    if len(tops) < 4:
        return FLAT, 0.0
    half = len(tops) // 2
    early = sum(tops[:half]) / half
    late = sum(tops[len(tops) - half:]) / half
    if early == 0:
        return (GROW, 1.0) if late > 0 else (FLAT, 0.0)
    change = (late - early) / early
    if change >= TREND_SLOPE:
        return GROW, change
    if change <= -TREND_SLOPE:
        return SHRINK, change
    return FLAT, change


# 점수의 가중치. 화면에 계산식을 적어야 하므로 단순하게 둔다. 이 점수는
# 예측이 아니라 관측 요약이다. 유형 단위로 검증하려 해 봤으나 라벨이 28건에
# 기저율이 89.3% 라, 어떤 점수도 찍기보다 낫다고 증명할 수 없다. 예측으로
# 쓰려면 상품 단위로 가야 한다.
W_GROWTH, W_STREAK, W_SPREAD = 0.5, 0.3, 0.2


def type_score(track: dict) -> dict:
    """유형 점수와 하위 점수 셋.

    추세  TOP100 안 상품 수가 앞 절반 대비 뒤 절반에 얼마나 늘었나
    연속  몇 주째 트렌드 후보인가
    분산  오른 상품이 몇 개 브랜드에 퍼져 있나
    """
    ch = track["change"]
    growth = 100 if ch >= 0.5 else 70 if ch >= TREND_SLOPE else 40 if ch > -TREND_SLOPE else 10
    streak = min(track["streak"], 5) / 5 * 100
    tops, brands = track["tops"][-1], track["brands"][-1]
    spread = min(brands / tops, 1.0) * 100 if tops else 0.0
    return {
        "score": round(growth * W_GROWTH + streak * W_STREAK + spread * W_SPREAD),
        "parts": {"growth": round(growth), "streak": round(streak),
                  "spread": round(spread)},
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=None)
    ap.add_argument("--weeks", type=int, default=6, help="최대 몇 주를 볼지")
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args(argv)

    conn = storage.connect(args.db)
    days = snapshot_days(conn)
    chain = weekly_chain(days, args.weeks)
    if len(chain) < 3:
        print(f"주간 비교에 쓸 수 있는 수집일이 {len(chain)}개뿐이다. "
              f"최소 3개가 있어야 궤적을 그린다")
        return 1

    weeks = [(chain[i], chain[i + 1]) for i in range(len(chain) - 1)]
    print(f"29CM 상의 TOP100, {chain[0]} 부터 {chain[-1]} 까지 {len(weeks)}주\n")

    snaps = [(d, week_snapshot(conn, pd, d)) for pd, d in weeks]
    types = sorted({t for _, s in snaps for t in s},
                   key=lambda t: -sum(s.get(t, {}).get("n_rise", 0) for _, s in snaps))

    head = ("  " + f"{'유형':<8}" + "".join(f"{d[5:]:>9}" for d, _ in snaps)
            + "   연속    방향   변화   점수")
    print(head)
    print("  " + "-" * (len(head) - 2))
    track = {}
    for t in types:
        cells, streak, best, shares = [], 0, 0, []
        for _, s in snaps:
            v = s.get(t, {}).get("verdict", NONE)
            n = s.get(t, {}).get("n_rise", 0)
            top = s.get(t, {}).get("n_top", 0)
            cells.append(f"{MARK[v]} {n:>2}")
            shares.append(n / top if top else 0.0)
            streak = streak + 1 if v == CAND else 0
            best = max(best, streak)
        dirn, change = direction([s.get(t, {}).get("n_top", 0) for _, s in snaps])
        print(f"  {t:<8}" + "".join(f"{c:>9}" for c in cells)
              + f"{best:>6}주  {dirn:>6} {change:>+6.0%}", end="")
        track[t] = {
            "weeks": [d for d, _ in snaps],
            "verdicts": [s.get(t, {}).get("verdict", NONE) for _, s in snaps],
            "rises": [s.get(t, {}).get("n_rise", 0) for _, s in snaps],
            "brands": [s.get(t, {}).get("n_brand", 0) for _, s in snaps],
            "tops": [s.get(t, {}).get("n_top", 0) for _, s in snaps],
            "shares": [round(x, 3) for x in shares],
            "streak": best,
            "direction": dirn,
            "change": round(change, 3),
        }
        track[t].update(type_score(track[t]))
        print(f"{track[t]['score']:>7}")

    print()
    rising = [t for t, v in track.items()
              if v["streak"] >= 3 and v["direction"] == GROW]
    flat = [t for t, v in track.items()
            if v["streak"] >= 3 and v["direction"] != GROW]
    print(f"  여러 주 후보이면서 확대  {', '.join(rising) if rising else '없음'}")
    print(f"  여러 주 후보이지만 제자리나 축소  {', '.join(flat) if flat else '없음'}")
    print()
    print("  아래쪽은 원래 큰 카테고리라 매주 서넛은 오르는 것이지 새로 뜨는")
    print("  것이 아니다. 한 주 판정만 보면 둘이 같은 '트렌드 후보' 로 보인다.")
    print("  방향은 TOP100 안 상품 수로 잰다. 유행하는 유형은 상위권에 들어오는")
    print("  상품 자체가 늘어난다.")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(track, ensure_ascii=False, indent=1),
                             encoding="utf-8")
        print(f"\n{args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
