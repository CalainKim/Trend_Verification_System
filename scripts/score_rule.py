#!/usr/bin/env python3
"""규칙만으로 판정해서 채점한다. 모델과 견주는 대조군이다.

모델이 기저율보다 나은지를 보려면 기저율만으로는 모자라다. 찍기보다 낫다고
해도 "그 정도는 규칙으로도 되는데" 일 수 있다. 규칙 점수를 같이 재면
리즈닝 모델이 실제로 보태는 게 있는지 알 수 있다.

    ./scripts/score_rule.py --benchmark benchmark
    ./scripts/score_rule.py --benchmark benchmark --cut 55

점수는 케이스 번들의 features 만 쓴다. 정답은 보지 않는다. 문턱을 정답에
맞춰 고르면 그 순간 과적합이라 채점이 뜻을 잃으므로, 기본값을 먼저 고정하고
결과를 본다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

# 가중치는 손으로 정했다. 정답을 보고 맞춘 것이 아니다. 근거는 이렇다.
#   상승폭   클수록 되돌아갈 여지도 크지만, 작은 상승은 애초에 잡음이다
#   리뷰     구매를 거쳐야 쌓이므로 조작 여지가 가장 적다
#   할인     늘었다면 순위 상승의 대체 설명이 된다. 지난주 검증에서 지속성과
#            차이가 없었으므로 감점을 작게 둔다
#   계절성   작년에도 올랐다면 올해만의 신호가 아니다
W = {"rise": 0.35, "review": 0.30, "discount": 0.15, "season": 0.20}


def clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    """값을 lo 와 hi 사이로 자른다."""
    return max(lo, min(hi, x))


def product_score(f: Dict[str, object], season: Optional[float]) -> Dict[str, object]:
    """0~100 점과 하위 점수. features 에 없는 항목은 50 으로 둔다.

    없는 값을 0 으로 두면 자료가 없는 것이 나쁜 신호로 바뀐다. 가운데에 두면
    그 항목이 판정을 밀지도 당기지도 않는다.
    """
    rise = f.get("rank_rise")
    review = f.get("review_delta")
    disc = f.get("sale_percent_delta")

    parts = {
        # 10계단이 감지 문턱이고 40계단이면 충분히 크다고 본다
        "rise": clamp((float(rise) - 10) / 30 * 100) if rise is not None else 50.0,
        # 리뷰가 20건 늘면 만점
        "review": clamp(float(review) / 20 * 100) if review is not None else 50.0,
        # 할인이 늘었으면 감점, 줄었는데도 올랐으면 가점
        "discount": clamp(50 - float(disc) * 2) if disc is not None else 50.0,
        # 작년 대비 1.0 배면 계절성, 1.5 배 이상이면 올해만의 움직임
        "season": clamp((season - 1.0) / 0.5 * 100) if season is not None else 50.0,
    }
    total = sum(parts[k] * W[k] for k in W)
    return {"score": round(total), "parts": {k: round(v) for k, v in parts.items()}}


def season_of(case: dict) -> Optional[float]:
    """근거 문장에서 작년 대비 배수를 읽는다. features 에는 없다."""
    import re

    for e in case.get("evidence", []):
        if e.get("id") == "seasonality":
            m = re.search(r"([0-9.]+) 배", e.get("observation", ""))
            if m:
                return float(m.group(1))
    return None


def main(argv=None) -> int:
    """숫자 규칙만으로 점수를 매기고 채점한다. AI 판정과 비교할 기준선이다."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--benchmark", type=Path, default=ROOT / "benchmark")
    ap.add_argument("--cut", type=float, default=50.0,
                    help="이 점수 이상이면 지속으로 본다")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    cases = sorted((args.benchmark / "cases").glob("*.json"))
    if not cases:
        raise SystemExit(f"{args.benchmark}/cases 에 케이스가 없다")

    verdicts, scores = {}, {}
    for f in cases:
        case = json.loads(f.read_text(encoding="utf-8"))
        got = product_score(case.get("features") or {}, season_of(case))
        scores[case["case_id"]] = got
        verdicts[case["case_id"]] = "WATCH" if got["score"] >= args.cut else "NOT_SUPPORTED"

    out = args.out or ROOT / "runs" / f"{args.benchmark.name}-rule-cut{int(args.cut)}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "verdicts.json").write_text(
        json.dumps(verdicts, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "scores.json").write_text(
        json.dumps(scores, ensure_ascii=False, indent=1), encoding="utf-8")

    vals = sorted(s["score"] for s in scores.values())
    n_watch = sum(1 for v in verdicts.values() if v == "WATCH")
    print(f"케이스 {len(cases)}건, 문턱 {args.cut:.0f}점")
    print(f"  점수 중앙값 {vals[len(vals)//2]}, 범위 {vals[0]} ~ {vals[-1]}")
    print(f"  지속 {n_watch}건, 소멸 {len(verdicts) - n_watch}건")
    print(f"\n채점하려면")
    print(f"  ./scripts/score_verdicts.py --benchmark {args.benchmark} "
          f"--verdicts {out / 'verdicts.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
