#!/usr/bin/env python3
"""지속성 케이스와 기저율을 만든다.

    python scripts/build_persistence_cases.py --stats        # 통계만 본다
    python scripts/build_persistence_cases.py --out benchmark
    python scripts/build_persistence_cases.py --step 21      # 독립 표본만

문제지(cases)에는 정답이 들어가지 않는다. 정답은 labels.sealed.json 에만 둔다.
검증 파트가 정답을 보고 끼워 맞추는 것을 막기 위해서이고, 이는 역추적 케이스에서
label 을 trend_case 에만 두는 규칙과 같다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trend_pipeline import persistence as ps, storage  # noqa: E402


def wilson(k: int, n: int, z: float = 1.96):
    """비율의 신뢰구간. 표본이 작을 때 정규근사보다 덜 틀린다."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def required_n(p: float, delta: float, z_a: float = 1.96, z_b: float = 0.8416) -> int:
    """기저율보다 delta 만큼 나은 모델을 가려내려면 필요한 표본 수."""
    return math.ceil((z_a + z_b) ** 2 * p * (1 - p) / (delta ** 2))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="지속성 케이스 생성")
    p.add_argument("--db", default=None)
    p.add_argument("--base", type=int, default=7, help="기준 구간 일수")
    p.add_argument("--detect", type=int, default=7, help="관측 구간 일수")
    p.add_argument("--hold", type=int, default=7, help="확인 구간 일수")
    p.add_argument("--step", type=int, default=1, help="창을 미는 간격")
    p.add_argument("--min-rise", type=float, default=ps.MIN_RISE)
    p.add_argument("--since", default="2026-09-29", help="연속 수집 시작일")
    p.add_argument("--out", default=None, help="케이스를 저장할 경로")
    p.add_argument("--stats", action="store_true", help="통계만 출력")
    args = p.parse_args(argv)

    conn = storage.connect(Path(args.db) if args.db else None)
    conn.row_factory = sqlite3.Row
    series = ps.load_series(conn)
    days = [d for d in ps.observed_days(series) if d >= args.since]
    span = args.base + args.detect + args.hold
    if len(days) < span:
        print(f"연속 구간이 {len(days)}일뿐이라 {span}일 창을 만들 수 없다.")
        return 1

    wins = ps.windows(days, args.base, args.detect, args.hold, args.step)
    indep = ps.windows(days, args.base, args.detect, args.hold, span)
    print(f"연속 수집 {len(days)}일: {days[0]} ~ {days[-1]}")
    print(f"창 구성 {args.base}+{args.detect}+{args.hold}일, 간격 {args.step}일")
    print(f"  겹친 창 {len(wins)}개 / 독립 창 {len(indep)}개\n")

    cases, labels = [], {}
    for wi, w in enumerate(wins):
        events = ps.rise_events(series, w, args.min_rise)
        got = ps.label_events(series, w, events)
        for e in events:
            if e.item_key not in got:
                continue
            cid = f"rise_{w.t_cut}_{e.item_key.replace(':', '_')}"
            # 키 이름은 검증 파트 파이프라인(src/trend_poc/review.py)의
            # build_payload 화이트리스트에 맞춘다. simulated_cutoff, evidence,
            # candidate, limitations 가 없으면 그 파이프라인에 넣을 수 없다.
            cases.append({
                "case_id": cid,
                "window_id": wi,                 # 겹친 창을 묶어 보려면 필요하다
                "experiment_type": "persistence-v1",
                "candidate": {
                    "keyword": e.name,
                    "definition": f"29CM 상의 카테고리 랭킹에 오른 개별 상품이다. "
                                  f"브랜드는 '{e.brand}' 다. 품목 키워드가 아니라 "
                                  f"상품 하나이므로, 같은 속성을 가진 다른 상품의 "
                                  f"움직임은 이 번들에 들어 있지 않다.",
                },
                "claim": f"{w.t_cut} 까지의 자료로 볼 때, 이 상품의 순위 상승이 "
                         f"이후 {args.hold}일 동안 절반 이상 유지되겠는가?",
                "simulated_cutoff": w.t_cut,
                "t_cut": w.t_cut,
                "horizon_days": args.hold,
                "historical_available_at": None,
                "item": {"key": e.item_key, "name": e.name, "brand": e.brand},
                "features": e.features(),
                "evidence": e.evidence(w),
                "limitations": ps.LIMITATIONS,
            })
            labels[cid] = got[e.item_key]

    counts = Counter(labels.values())
    n = len(labels)
    if n == 0:
        print("상승 이벤트가 없다.")
        return 1
    k = counts[ps.PERSIST]
    rate = k / n
    lo, hi = wilson(k, n)
    print(f"=== 케이스 {n}건 ===")
    print(f"  지속 {k}건 / 소멸 {counts[ps.FADE]}건")
    print(f"  기저율 {rate:.1%}   95% 신뢰구간 [{lo:.1%}, {hi:.1%}]  폭 {(hi-lo)*100:.1f}%p\n")

    print("=== 모델이 기저율보다 낫다고 말하려면 ===")
    for d in (0.20, 0.15, 0.10, 0.05):
        need = required_n(rate, d)
        mark = "충분" if n >= need else f"부족 ({need - n}건 더)"
        print(f"  +{d*100:>2.0f}%p 탐지에 {need:>4}건 필요   현재 {n}건  {mark}")

    ind_n = len({c["window_id"] for c in cases})
    print(f"\n주의. 창이 겹치므로 {n}건이 전부 독립은 아니다. "
          f"독립 창은 {len(indep)}개이고 케이스는 {ind_n}개 창에서 나왔다.")
    print("통계적 주장을 할 때는 --step 을 창 전체 길이로 주고 다시 세어야 한다.")

    if args.stats or not args.out:
        return 0

    out = Path(args.out)
    (out / "cases").mkdir(parents=True, exist_ok=True)
    for c in cases:
        (out / "cases" / f"{c['case_id']}.json").write_text(
            json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
    sealed = json.dumps({"base_rate": rate, "n": n, "labels": labels},
                        ensure_ascii=False, sort_keys=True, indent=2)
    (out / "labels.sealed.json").write_text(sealed, encoding="utf-8")

    # 정답 파일은 저장소에 올리지 않는다. 검증 파트가 보면 블라인드가 깨진다.
    # 대신 해시만 남겨 두고, 채점이 끝난 뒤 정답을 바꾸지 않았음을 증명한다.
    digest = hashlib.sha256(sealed.encode("utf-8")).hexdigest()
    (out / "labels.digest.txt").write_text(
        f"sha256  {digest}\nn       {n}\nbase    {rate:.6f}\n", encoding="utf-8")
    print(f"\n케이스 {len(cases)}건을 {out/'cases'} 에 저장했다.")
    print(f"정답은 {out/'labels.sealed.json'} (저장소 제외), "
          f"봉인 해시는 {out/'labels.digest.txt'} 에 있다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
