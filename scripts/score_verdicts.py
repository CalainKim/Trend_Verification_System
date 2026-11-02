#!/usr/bin/env python3
"""판정을 채점한다.

    python scripts/score_verdicts.py --verdicts runs/2026-11-01
    python scripts/score_verdicts.py --baselines          # 기준 전략만 본다
    python scripts/score_verdicts.py --verdicts x --out benchmark/scorecard.md

판정 파일은 세 형태를 받는다.
  1. 디렉터리 안의 <case_id>.json       {"verdict": "WATCH"}
  2. 검증 파트 산출물 result.json       review.verdict 또는 selection.status
  3. 하나의 매핑 파일                   {"<case_id>": "WATCH", ...}

정답 파일은 저장소에 없다. 수집 파트만 가지고 있고, 봉인 해시로 바뀌지
않았음을 확인한다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trend_pipeline import scoring as sc  # noqa: E402
from trend_pipeline.persistence import FADE, PERSIST  # noqa: E402

DEFAULT_BENCH = ROOT / "benchmark"


def load_labels(bench: Path = DEFAULT_BENCH) -> Dict[str, str]:
    """정답을 읽고 봉인 해시를 확인한다.

    채점이 끝난 뒤 정답을 고치면 어떤 점수든 만들 수 있다. 해시가 맞지
    않으면 채점을 진행하지 않는다.
    """
    sealed, digest = bench / "labels.sealed.json", bench / "labels.digest.txt"
    if not sealed.exists():
        raise SystemExit(f"정답 파일이 없다: {sealed}\n"
                         f"scripts/build_persistence_cases.py 로 먼저 만든다.")
    raw = sealed.read_text(encoding="utf-8")
    if digest.exists():
        stated = digest.read_text(encoding="utf-8").split()[1]
        actual = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        if stated != actual:
            raise SystemExit(
                f"봉인 해시가 맞지 않는다. 정답이 바뀌었다.\n"
                f"  기록 {stated}\n  실제 {actual}")
    return json.loads(raw)["labels"]


def _verdict_from(obj) -> str:
    """여러 산출물 형식에서 판정 값을 꺼낸다."""
    if isinstance(obj, str):
        return obj
    if not isinstance(obj, dict):
        raise ValueError(f"판정을 읽을 수 없는 형식이다: {type(obj).__name__}")
    for path in (("verdict",), ("review", "verdict"), ("review", "status"),
                 ("selection", "status"), ("status",)):
        cur = obj
        for key in path:
            if not isinstance(cur, dict) or key not in cur:
                cur = None
                break
            cur = cur[key]
        if isinstance(cur, str) and cur.strip() and cur != "not_run":
            return cur
    raise ValueError(f"판정 값을 찾지 못했다. 본 키: {sorted(obj)[:6]}")


def load_verdicts(path: Path) -> Dict[str, str]:
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise SystemExit("매핑 파일은 {case_id: verdict} 형태여야 한다.")
        return {k: _verdict_from(v) for k, v in data.items()}

    out: Dict[str, str] = {}
    for f in sorted(path.rglob("*.json")):
        if f.name in ("bundle.json", "labels.sealed.json"):
            continue
        try:
            obj = json.loads(f.read_text(encoding="utf-8"))
            cid = obj.get("case_id") if isinstance(obj, dict) else None
            out[cid or f.stem] = _verdict_from(obj)
        except (ValueError, KeyError):
            continue          # 판정이 아닌 파일은 건너뛴다
    if not out:
        raise SystemExit(f"{path} 에서 판정을 찾지 못했다.")
    return out


def render(card: sc.Scorecard, title: str) -> str:
    L = [f"## {title}", ""]
    L.append(f"- 케이스 {card.n_cases}건, 답변 {card.n_answered}건, "
             f"기권 {card.n_abstained}건 (커버리지 {card.coverage:.1%})")
    if card.accuracy is None:
        L.append("- 답한 케이스가 없어 채점할 수 없다")
        return "\n".join(L)
    L.append(f"- 정확도 {card.accuracy:.1%} "
             f"(95% 신뢰구간 {card.ci[0]:.1%} ~ {card.ci[1]:.1%})")
    L.append(f"- 기저율 전체 {card.base_rate_all:.1%}, "
             f"답한 부분 {card.base_rate_answered:.1%}")
    L.append(f"- 기저율 대비 {card.lift * 100:+.1f}%p")
    L.append(f"- 기저율을 유의하게 넘었나: "
             f"**{'그렇다' if card.beats_base_rate else '아니다'}** "
             f"(신뢰구간 아래끝 {card.ci[0]:.1%} vs 기저율 "
             f"{card.base_rate_answered:.1%})")
    if card.confusion:
        L.append("")
        L.append("| 정답 | 예측 | 건수 |")
        L.append("|---|---|---|")
        for k in sorted(card.confusion):
            t, p = k.split("->")
            L.append(f"| {t} | {p} | {card.confusion[k]} |")
    for n in card.notes:
        L.append(f"\n> {n}")
    return "\n".join(L)


def baselines(labels: Dict[str, str]) -> str:
    """찍기 전략들의 점수. 모델은 이것을 넘어야 뜻이 있다."""
    rng = random.Random(20261029)
    strategies = {
        "전부 지속": {c: PERSIST for c in labels},
        "전부 소멸": {c: FADE for c in labels},
        "무작위 (고정 시드)": {c: rng.choice([PERSIST, FADE]) for c in labels},
        "전부 보류": {c: "HOLD" for c in labels},
    }
    out = ["## 기준 전략", "",
           "모델 성적은 이 값들과 비교해야 뜻이 있다.", "",
           "| 전략 | 커버리지 | 정확도 | 기저율 대비 |", "|---|---|---|---|"]
    for name, v in strategies.items():
        card = sc.score(labels, v)
        acc = f"{card.accuracy:.1%}" if card.accuracy is not None else "-"
        lift = f"{card.lift * 100:+.1f}%p" if card.lift is not None else "-"
        out.append(f"| {name} | {card.coverage:.0%} | {acc} | {lift} |")
    return "\n".join(out)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="판정 채점")
    p.add_argument("--verdicts", default=None, help="판정 파일이나 디렉터리")
    p.add_argument("--benchmark", default=str(DEFAULT_BENCH),
                   help="정답이 있는 벤치마크 경로")
    p.add_argument("--label", default="판정 결과", help="성적표 제목")
    p.add_argument("--baselines", action="store_true", help="기준 전략만 출력")
    p.add_argument("--out", default=None, help="성적표를 쓸 경로")
    args = p.parse_args(argv)

    labels = load_labels(Path(args.benchmark))
    parts = [baselines(labels)]

    if args.verdicts:
        verdicts = load_verdicts(Path(args.verdicts))
        card = sc.score(labels, verdicts)
        parts.insert(0, render(card, args.label))
    elif not args.baselines:
        parts.append("\n판정 경로를 주지 않았다. --verdicts 로 지정한다.")

    text = "\n\n".join(parts)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"\n성적표를 {args.out} 에 저장했다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
