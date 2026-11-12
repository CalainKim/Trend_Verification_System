#!/usr/bin/env python3
"""과거 시점으로 돌아가 그때 오른 것이 어떻게 됐는지 모은다.

    ./.venv/bin/python scripts/build_retrospect.py -o build/retrospect.json

벤치마크와 같은 자료를 쓰지만 반대로 쓴다. 벤치마크는 확인 구간을 가리고
모델에게 맞혀 보라고 한다. 회고는 확인 구간을 펼쳐서 사람에게 보여 준다.
채점이 아니라 설득이 목적이다.

**공개 벤치마크만 쓴다.** 봉인한 둘(benchmark, benchmark-index)로 만들면
화면에 정답이 그려지고, 그 화면을 저장소에 올리는 순간 블라인드가 깨진다.
검증 파트가 보면 안 되는 것을 화면으로 흘리는 일은 오류가 나지 않아 발견이
어렵다. 그래서 경로를 인자로 받지 않고 상수로 박았다.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trend_pipeline import persistence as ps  # noqa: E402
from trend_pipeline import storage  # noqa: E402

#: 정답이 저장소에 공개된 벤치마크. 이것만 회고로 펼칠 수 있다.
OPEN_BENCH = ROOT / "benchmark-index-long"

#: build_all_benchmarks.sh 의 3번과 같은 설정이어야 한다. 다르면 회고에
#: 나오는 상승이 벤치마크의 상승과 달라져서 두 숫자가 어긋난다.
CHANNEL = "gtrends"
ENTITIES = ("geo=KR", "geo=US", "geo=WORLD")
BASE, DETECT, HOLD, STEP = 8, 4, 12, 24

GEO_NAME = {"geo=KR": "한국", "geo=US": "미국", "geo=WORLD": "전세계"}


def curve(item: Dict[str, float], days: List[str]) -> List[dict]:
    """그릴 점들. 관측이 없는 주는 값을 None 으로 남긴다.

    빼 버리면 선이 이어져서 결측이 안 보인다. 결측 구간의 추세를 읽으면
    안 되는데 그림만 보면 읽게 된다.
    """
    return [{"d": d, "v": item.get(d)} for d in days]


def main(argv=None) -> int:
    """지난 시점마다 무엇이 보였고 그 뒤 어떻게 됐는지 회고 자료(JSON)를 만든다."""
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("-o", "--out", default="build/retrospect.json")
    p.add_argument("--db", default=None)
    p.add_argument("--design", default=None,
                   help="Claude Design 에 붙여넣을 줄인 사본을 쓸 경로. "
                        "전부 넣으면 600KB 라 붙여넣기가 안 된다")
    p.add_argument("--design-moments", type=int, default=3)
    p.add_argument("--design-rows", type=int, default=8)
    args = p.parse_args(argv)

    sealed = json.loads((OPEN_BENCH / "labels.sealed.json").read_text("utf-8"))
    labels = sealed["labels"]

    conn = storage.connect(Path(args.db) if args.db else None)
    conn.row_factory = sqlite3.Row
    series = ps.load_index_series(conn, CHANNEL, ENTITIES)
    days = ps.observed_days(series)
    wins = ps.windows(days, BASE, DETECT, HOLD, STEP)
    print(f"관측점 {len(days)}개: {days[0]} ~ {days[-1]}")
    print(f"창 {len(wins)}개 (간격 {STEP}주)")

    moments, n_cases, n_missing = [], 0, 0
    for wi, w in enumerate(wins):
        events = ps.index_rise_events(series, w)
        rows = []
        for e in sorted(events, key=lambda x: -x.rise_ratio):
            case_id = f"idx_{CHANNEL}_{w.t_cut}_{e.keyword}@{e.entity.replace('=', '')}"
            label = labels.get(case_id)
            if label is None:
                # 정답이 없는 상승은 확인 구간 관측이 모자라 라벨이 안 붙은
                # 것이다. 결과를 모르니 회고에 넣으면 빈 칸이 생긴다.
                n_missing += 1
                continue
            item = series[e.key]
            hm, _ = ps._mean(item, w.hold)
            rows.append({
                "case_id": case_id,
                "keyword": e.keyword,
                "geo": GEO_NAME.get(e.entity, e.entity),
                "base_mean": round(e.base_mean, 1),
                "detect_mean": round(e.detect_mean, 1),
                "hold_mean": round(hm, 1) if hm is not None else None,
                "rise_pct": round((e.rise_ratio - 1) * 100, 1),
                "yoy_ratio": round(e.yoy_ratio, 2) if e.yoy_ratio is not None else None,
                "coverage": round(e.coverage, 2),
                "outcome": label,
                "before": curve(item, w.base + w.detect),
                "after": curve(item, w.hold),
            })
        if not rows:
            continue
        n_cases += len(rows)
        kept = sum(1 for r in rows if r["outcome"] == ps.PERSIST)
        moments.append({
            "t_cut": w.t_cut,
            "base_from": w.base[0], "detect_to": w.detect[-1],
            "hold_to": w.hold[-1],
            "n_rise": len(rows), "n_persist": kept,
            "persist_rate": round(kept / len(rows), 3),
            "rows": rows,
        })

    out = {
        "_note": "과거 시점별로 그때 오른 검색어와 그 뒤 결과. "
                 "정답이 공개된 benchmark-index-long 으로만 만든다.",
        "channel": CHANNEL,
        "window": {"base": BASE, "detect": DETECT, "hold": HOLD,
                   "unit": "주", "step": STEP},
        "moments": moments,
    }
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), "utf-8")

    if args.design:
        # 디자인은 숫자가 몇 개 있느냐가 아니라 어떤 모양이냐를 본다. 가장
        # 잘 버틴 시점과 가장 안 버틴 시점을 넣어야 양극단이 화면에서 어떻게
        # 보이는지 알 수 있다. 가운데도 하나 넣는다.
        order = sorted(moments, key=lambda m: m["persist_rate"])
        picks = [order[0], order[len(order) // 2], order[-1]][:args.design_moments]
        small = []
        for m in sorted(picks, key=lambda x: x["t_cut"]):
            rows = m["rows"][:args.design_rows]
            small.append({**m, "rows": rows,
                          "_note_rows": f"실제로는 {m['n_rise']}건이고 "
                                        f"여기엔 {len(rows)}건만 넣었다"})
        d = Path(args.design)
        d.parent.mkdir(parents=True, exist_ok=True)
        d.write_text(json.dumps(
            {**out, "_note": out["_note"] + " 디자인용으로 줄인 사본이다.",
             "moments": small}, ensure_ascii=False, indent=1), "utf-8")
        print(f"디자인용 사본 {d}  {d.stat().st_size / 1024:.0f}KB")

    print(f"\n시점 {len(moments)}개, 상승 {n_cases}건")
    if n_missing:
        print(f"확인 구간 관측이 모자라 라벨이 없는 상승 {n_missing}건은 뺐다")
    print(f"\n{path}")
    for m in moments:
        print(f"  {m['t_cut']}  상승 {m['n_rise']:3}건  "
              f"지속 {m['n_persist']:3}건 ({m['persist_rate']:.0%})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
