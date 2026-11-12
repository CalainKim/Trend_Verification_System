#!/usr/bin/env python3
"""벤치마크 케이스를 검증 파트의 판정기에 넣는다.

검증 파트(src/trend_poc/review.py)가 내는 WATCH, HOLD, NOT_SUPPORTED 는
채점기(scripts/score_verdicts.py)가 그대로 받는 어휘다. 케이스 파일도 판정기가
읽는 키 여덟 개를 모두 갖고 있어 변환이 필요 없다. 이 스크립트는 둘을 잇기만
한다.

    ./.venv/bin/python scripts/review_cases.py --benchmark benchmark --n 30 --dry-run
    ./.venv/bin/python scripts/review_cases.py --benchmark benchmark --n 30
    ./.venv/bin/python scripts/score_verdicts.py --verdicts runs/<이름>/verdicts.json

    venv 의 python 으로 불러야 한다. ./scripts/review_cases.py 로 바로 부르면
    shebang 이 시스템 python 을 잡고, 거기에는 Anthropic SDK 가 없어서 61건이
    전부 0초 만에 실패한다. 규칙 판정(--dry-run)은 SDK 를 안 쓰므로 그대로
    통과해서, 배선을 확인했다고 착각하기 쉽다.

--dry-run 은 API 를 부르지 않고 배선만 확인한다. 실제 실행은 케이스마다 한 번씩
모델을 부르므로 돈이 든다. 먼저 적은 수로 돌려 보고 늘린다.

판정기는 같은 입력을 두 번 청구하지 않는다. 케이스마다 디렉터리를 따로 두고
review.json 이 이미 있으면 그대로 돌려준다. 중간에 끊겨도 받은 만큼은 남는다.

정답 파일은 읽지 않는다. 판정기에 정답이 흘러 들어가면 채점이 뜻을 잃는다.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trend_poc.review import run_review  # noqa: E402

VALID = {"WATCH", "HOLD", "NOT_SUPPORTED"}


class StubClient:
    """배선 확인용. 모델을 부르지 않고 규칙으로 답한다.

    이것은 기준선이 아니다. 상승폭이 크면 WATCH 라고 할 뿐이고, 그 규칙이
    맞는지는 아무도 확인하지 않았다. 케이스가 판정기를 지나 채점기까지 흘러
    가는지만 본다.

    커머스 케이스에는 검색 교차 특징이 아예 없다. 브랜드 동반 상승은 있지만
    지난주 검증에서 반대 방향으로 나왔으므로(동시 상승 62.5% 유지, 단독 51.5%)
    규칙에 쓰지 않는다. 기각된 가설로 판정하면 기준선이라고 부를 수 없다.
    """

    MODEL = "claude-opus-5-5"

    def __init__(self):
        self.calls = 0

    def generate(self, payload, checkpoint=None):
        """돈이 드는 AI 대신 숫자 규칙으로 가짜 판정을 낸다. 실제 호출 전에 흐름을 시험할 때 쓴다."""
        self.calls += 1
        ctx = json.loads(payload["messages"][0]["content"])
        f = ctx.get("features") or {}
        if "rise_ratio" in f:                       # 검색 지수 케이스
            x, name, cut = f.get("rise_ratio"), "상승 배수", 1.5
        else:                                       # 커머스 순위 케이스
            x, name, cut = f.get("rank_rise"), "상승 계단", 20.0
        if x is None:
            v, why = "HOLD", f"{name} 를 잴 수 없다"
        elif x >= cut:
            v, why = "WATCH", f"{name} {x} 로 문턱 {cut} 이상이다"
        else:
            v, why = "NOT_SUPPORTED", f"{name} {x} 로 문턱 {cut} 에 못 미친다"
        return {"text": json.dumps(
            {"verdict": v, "summary": why,
             "support": [], "against": [], "unknowns": []}, ensure_ascii=False),
            "stop_reason": "end_turn", "usage_complete": True,
            "actual_model": self.MODEL}


def pick(benchmark: Path, n: int, seed: int) -> List[Path]:
    """케이스를 고른다. 앞에서부터 자르면 한 주에 몰려서 치우친다."""
    cases = sorted((benchmark / "cases").glob("*.json"))
    if not cases:
        raise SystemExit(f"{benchmark}/cases 에 케이스가 없다")
    if n >= len(cases):
        return cases
    rng = random.Random(seed)
    return sorted(rng.sample(cases, n))


def main(argv=None) -> int:
    """벤치마크에서 사례를 뽑아 AI 판정을 받는다. --dry-run 이면 가짜 판정기로 돈 없이 돌린다."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--benchmark", type=Path, default=ROOT / "benchmark")
    ap.add_argument("--n", type=int, default=30, help="판정할 케이스 수")
    ap.add_argument("--seed", type=int, default=20261102, help="케이스 추첨 씨앗")
    ap.add_argument("--run-dir", type=Path, default=None)
    ap.add_argument("--dry-run", action="store_true",
                    help="API 를 부르지 않고 규칙으로 답한다. 배선 확인과 기준선용")
    args = ap.parse_args(argv)

    cases = pick(args.benchmark, args.n, args.seed)
    tag = "stub" if args.dry_run else "model"
    run_dir = args.run_dir or ROOT / "runs" / f"{args.benchmark.name}-{tag}-{args.seed}"
    client = StubClient() if args.dry_run else None

    print(f"{args.benchmark.name} 에서 {len(cases)}건을 뽑았다")
    print(f"판정기 {'규칙 (API 안 부름)' if args.dry_run else '모델 (API 호출, 비용 발생)'}")
    print(f"결과는 {run_dir}\n")

    verdicts: Dict[str, str] = {}
    fail = []
    for i, f in enumerate(cases, 1):
        bundle = json.loads(f.read_text(encoding="utf-8"))
        cid = bundle["case_id"]
        try:
            rec = run_review(ROOT, run_dir / cid, bundle, client=client)
        except Exception as exc:
            fail.append((cid, f"{type(exc).__name__}: {exc}"))
            continue
        v = (rec.get("result") or {}).get("verdict")
        if v not in VALID:
            fail.append((cid, f"판정이 {v!r} 다"))
            continue
        verdicts[cid] = v
        if i % 10 == 0 or i == len(cases):
            print(f"  {i}/{len(cases)}  판정 {len(verdicts)}건, 실패 {len(fail)}건")

    if fail:
        print(f"\n실패 {len(fail)}건")
        for cid, why in fail[:5]:
            print(f"  {cid}  {why}")

    if not verdicts:
        print("\n판정이 하나도 안 나왔다. 채점할 것이 없다")
        return 1

    out = run_dir / "verdicts.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(verdicts, ensure_ascii=False, indent=1), encoding="utf-8")

    from collections import Counter
    c = Counter(verdicts.values())
    print(f"\n판정 {len(verdicts)}건  " + ", ".join(f"{k} {v}" for k, v in c.most_common()))
    print(f"\n채점하려면")
    print(f"  ./scripts/score_verdicts.py --benchmark {args.benchmark} --verdicts {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
